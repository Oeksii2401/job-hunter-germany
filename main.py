import os
import uuid
import json
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import asyncpg

from modules.db import init_db, get_session, update_session, save_sent_email
from modules.cv_parser import parse_cv, extract_pdf_text
from modules.job_search import find_companies_for_profile
from modules.cv_adapter import adapt_cv
from modules.email_writer import write_email, write_followup
from modules.email_sender import send_application, send_followup
from modules.scheduler import start_scheduler, stop_scheduler
from prompts.prompts import get_message

logging.basicConfig(level=logging.INFO)

app = FastAPI()

# ─────────────────────────────────────────────
# ACTIVE CONNECTIONS (session_id → websocket)
# ─────────────────────────────────────────────
active_connections: dict = {}

# ─────────────────────────────────────────────
# STARTUP / SHUTDOWN
# ─────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    from modules.db import init_db, db_pool
    await init_db()
    from modules.db import db_pool as pool
    start_scheduler(pool, notify_session)
    logging.info("App started")

@app.on_event("shutdown")
async def shutdown():
    stop_scheduler()

# ─────────────────────────────────────────────
# NOTIFY SESSION (для follow-up из scheduler)
# ─────────────────────────────────────────────
async def notify_session(session_id: str, event: str, data: dict):
    ws = active_connections.get(session_id)
    if not ws:
        return
    session = await get_session(session_id)
    lang = session.get("lang", "ru")
    company_name = data.get("company_name", "")

    if event == "followup_1":
        await ws.send_json({
            "type": "message",
            "sender": "bot",
            "text": get_message(lang, "followup_1", company=company_name),
            "buttons": ["да", "нет"] if lang == "ru" else ["yes", "no"]
        })
        await update_session(session_id, step=f"followup_1_{data['id']}")

    elif event == "followup_2":
        await ws.send_json({
            "type": "message",
            "sender": "bot",
            "text": get_message(lang, "followup_2", company=company_name),
            "buttons": ["да", "нет"] if lang == "ru" else ["yes", "no"]
        })
        await update_session(session_id, step=f"followup_2_{data['id']}")

# ─────────────────────────────────────────────
# PDF UPLOAD ENDPOINT
# ─────────────────────────────────────────────
@app.post("/upload-cv")
async def upload_cv(file: UploadFile = File(...), session_id: str = Form(...)):
    try:
        file_bytes = await file.read()
        text = await extract_pdf_text(file_bytes)
        if not text.strip():
            return {"status": "error", "message": "Не удалось извлечь текст из PDF"}
        return {"status": "ok", "text": text}
    except Exception as e:
        logging.error(f"Upload error: {e}")
        return {"status": "error", "message": str(e)}

# ─────────────────────────────────────────────
# WEBSOCKET
# ─────────────────────────────────────────────
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    active_connections[session_id] = websocket
    logging.info(f"WS connected: {session_id}")

    session = await get_session(session_id)
    lang = session.get("lang", "ru")

    # Приветствие на всех языках
    await websocket.send_json({
        "type": "message",
        "sender": "bot",
        "text": (
            "👋 Привет! / Hallo! / Hello! / Привіт! / مرحبا! / سلام!\n\n"
            "🇷🇺 Я — Job Hunter Germany. Помогу найти работу в Германии.\n"
            "🇩🇪 Ich bin Job Hunter Germany. Ich helfe dir, einen Job zu finden.\n"
            "🇬🇧 I am Job Hunter Germany. I'll help you find a job in Germany.\n"
            "🇺🇦 Я — Job Hunter Germany. Допоможу знайти роботу в Німеччині.\n"
            "🇸🇦 أنا Job Hunter Germany. سأساعدك في إيجاد عمل في ألمانيا.\n"
            "🇦🇫 زه Job Hunter Germany یم. زه به تاسو سره د کار موندلو کې مرسته وکړم.\n\n"
            "Выбери язык / Wähle Sprache / Choose language / Обери мову / اختر اللغة / ژبه غوره کړئ:"
        ),
        "buttons": ["🇷🇺 Русский", "🇩🇪 Deutsch", "🇬🇧 English",
                    "🇺🇦 Українська", "🇸🇦 العربية", "🇦🇫 پښتو"]
    })

    try:
        while True:
            data = await websocket.receive_json()
            session = await get_session(session_id)
            step = session.get("step", "lang")
            lang = session.get("lang", "ru")
            text = data.get("text", "").strip()

            # ── Выбор языка ──────────────────────────
            if step == "lang":
                lang_map = {
                    "🇷🇺 Русский": "ru", "🇩🇪 Deutsch": "de",
                    "🇬🇧 English": "en", "🇺🇦 Українська": "uk",
                    "🇸🇦 العربية": "ar", "🇦🇫 پښتو": "ps",
                }
                lang = lang_map.get(text, "ru")
                await update_session(session_id, lang=lang, step="upload_cv")
                await websocket.send_json({
                    "type": "message",
                    "sender": "bot",
                    "text": get_message(lang, "upload_cv"),
                    "show_upload": True
                })

            # ── Загрузка CV ───────────────────────────
            elif step == "upload_cv":
                cv_text = text
                if data.get("type") == "cv_uploaded":
                    cv_text = data.get("text", "")

                if not cv_text.strip():
                    await websocket.send_json({
                        "type": "message",
                        "sender": "bot",
                        "text": get_message(lang, "upload_cv"),
                        "show_upload": True
                    })
                    continue

                await update_session(session_id, cv_text=cv_text, step="parsing")
                await websocket.send_json({
                    "type": "message",
                    "sender": "bot",
                    "text": get_message(lang, "parsing")
                })

                # Парсим CV
                profile = await parse_cv(cv_text, lang)
                profile_json = json.dumps(profile, ensure_ascii=False)
                await update_session(session_id, cv_profile=profile_json, step="questions")

                hidden = ", ".join(profile.get("hidden_competencies", [])[:2])
                opportunities = ", ".join(profile.get("cross_domain_opportunities", [])[:2])

                await websocket.send_json({
                    "type": "message",
                    "sender": "bot",
                    "text": get_message(lang, "parsed_ok",
                        domain=profile.get("primary_domain", ""),
                        hidden=hidden or "—",
                        opportunities=opportunities or "—"
                    )
                })

                # Первый вопрос
                questions = profile.get("clarifying_questions", [])
                if questions:
                    await update_session(session_id,
                        step="questions",
                        cv_profile=json.dumps({**profile, "_q_index": 0}, ensure_ascii=False)
                    )
                    await websocket.send_json({
                        "type": "message",
                        "sender": "bot",
                        "text": get_message(lang, "question",
                            n=1, total=len(questions), question=questions[0]
                        )
                    })
                else:
                    await update_session(session_id, step="job_search")
                    await _do_job_search(websocket, session_id, lang, profile)

            # ── Уточняющие вопросы ────────────────────
            elif step == "questions":
                profile = json.loads(session.get("cv_profile") or "{}")
                questions = profile.get("clarifying_questions", [])
                q_index = profile.get("_q_index", 0)

                # Сохраняем ответ в профиле
                answers = profile.get("_answers", [])
                answers.append({"q": questions[q_index] if q_index < len(questions) else "", "a": text})
                profile["_answers"] = answers
                q_index += 1
                profile["_q_index"] = q_index

                await update_session(session_id, cv_profile=json.dumps(profile, ensure_ascii=False))

                if q_index < len(questions):
                    await websocket.send_json({
                        "type": "message",
                        "sender": "bot",
                        "text": get_message(lang, "question",
                            n=q_index + 1, total=len(questions),
                            question=questions[q_index]
                        )
                    })
                else:
                    await update_session(session_id, step="job_search")
                    await websocket.send_json({
                        "type": "message",
                        "sender": "bot",
                        "text": get_message(lang, "searching")
                    })
                    await _do_job_search(websocket, session_id, lang, profile)

            # ── Выбор компаний ────────────────────────
            elif step == "select_companies":
                companies = json.loads(session.get("companies") or "[]")
                try:
                    selected_nums = [int(n.strip()) - 1 for n in text.split(",") if n.strip().isdigit()]
                    selected = [companies[i] for i in selected_nums if 0 <= i < len(companies)]
                except Exception:
                    selected = []

                if not selected:
                    await websocket.send_json({
                        "type": "message",
                        "sender": "bot",
                        "text": "Введи номера компаний через запятую (например: 1, 3)"
                    })
                    continue

                await update_session(session_id,
                    selected_companies=json.dumps(selected, ensure_ascii=False),
                    step="adapt_cv"
                )
                await _process_next_company(websocket, session_id, lang, selected, 0)

            # ── Подтверждение письма ──────────────────
            elif step.startswith("review_"):
                idx = int(step.split("_")[1])
                selected = json.loads(session.get("selected_companies") or "[]")
                company = selected[idx]

                yes_words = ["да", "yes", "ja", "так", "هو", "نعم"]
                no_words = ["нет", "no", "нein", "ні", "لا", "نه"]
                edit_words = ["поправить", "edit", "korrigieren", "виправити", "تعديل", "سمول"]

                if any(w in text.lower() for w in yes_words):
                    await update_session(session_id, step=f"send_email_{idx}")
                    await websocket.send_json({
                        "type": "message",
                        "sender": "bot",
                        "text": get_message(lang, "confirm_send", company=company["name"])
                    })
                elif any(w in text.lower() for w in edit_words):
                    await websocket.send_json({
                        "type": "message",
                        "sender": "bot",
                        "text": "Напиши что нужно поправить в письме:"
                    })
                    await update_session(session_id, step=f"edit_letter_{idx}")
                else:
                    # Пропустить эту компанию
                    await _next_or_done(websocket, session_id, lang, selected, idx)

            # ── Отправка письма ───────────────────────
            elif step.startswith("send_email_"):
                idx = int(step.split("_")[2])
                selected = json.loads(session.get("selected_companies") or "[]")
                company = selected[idx]
                profile = json.loads(session.get("cv_profile") or "{}")
                to_email = text

                await websocket.send_json({
                    "type": "message",
                    "sender": "bot",
                    "text": get_message(lang, "sending")
                })

                # Берём адаптированные данные из company
                ok = await send_application(
                    to_email=to_email,
                    candidate_name=profile.get("name", "Kandidat"),
                    company_name=company["name"],
                    subject=company.get("_subject", f"Bewerbung — {profile.get('name', '')}"),
                    anschreiben=company.get("_anschreiben_de", ""),
                    lebenslauf=company.get("_lebenslauf_de", "")
                )

                if ok:
                    await save_sent_email(session_id, company["name"], to_email)
                    await websocket.send_json({
                        "type": "message",
                        "sender": "bot",
                        "text": get_message(lang, "sent_ok", company=company["name"])
                    })
                    await _next_or_done(websocket, session_id, lang, selected, idx)
                else:
                    await websocket.send_json({
                        "type": "message",
                        "sender": "bot",
                        "text": get_message(lang, "sent_error")
                    })

            # ── Follow-up ─────────────────────────────
            elif step.startswith("followup_"):
                yes_words = ["да", "yes", "ja", "так", "هو", "نعم"]
                if any(w in text.lower() for w in yes_words):
                    parts = step.split("_")
                    followup_num = int(parts[1])
                    email_id = int(parts[2])
                    # Отправка follow-up
                    await websocket.send_json({
                        "type": "message",
                        "sender": "bot",
                        "text": get_message(lang, "sending")
                    })
                await update_session(session_id, step="menu")

    except WebSocketDisconnect:
        active_connections.pop(session_id, None)
        logging.info(f"WS disconnected: {session_id}")

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
async def _do_job_search(websocket, session_id, lang, profile):
    await websocket.send_json({
        "type": "message",
        "sender": "bot",
        "text": get_message(lang, "searching")
    })

    companies = await find_companies_for_profile(profile)

    if not companies:
        await websocket.send_json({
            "type": "message",
            "sender": "bot",
            "text": get_message(lang, "no_companies")
        })
        return

    await update_session(session_id,
        companies=json.dumps(companies, ensure_ascii=False),
        step="select_companies"
    )

    company_list = "\n".join([
        f"{i+1}. {c['name']}\n   📍 {c.get('address', '')}\n   🌐 {c.get('website', '')}"
        for i, c in enumerate(companies)
    ])

    await websocket.send_json({
        "type": "message",
        "sender": "bot",
        "text": get_message(lang, "companies_found",
            count=len(companies), list=company_list
        )
    })

async def _process_next_company(websocket, session_id, lang, selected, idx):
    if idx >= len(selected):
        await websocket.send_json({
            "type": "message",
            "sender": "bot",
            "text": get_message(lang, "done", count=len(selected))
        })
        await update_session(session_id, step="done")
        return

    company = selected[idx]
    session = await get_session(session_id)
    cv_text = session.get("cv_text", "")
    profile = json.loads(session.get("cv_profile") or "{}")

    await websocket.send_json({
        "type": "message",
        "sender": "bot",
        "text": get_message(lang, "adapting", company=company["name"])
    })

    adapted = await adapt_cv(cv_text, profile, company, lang)

    await websocket.send_json({
        "type": "message",
        "sender": "bot",
        "text": get_message(lang, "writing_email", company=company["name"])
    })

    email_data = await write_email(profile, adapted, company, lang)

    # Сохраняем данные письма в компанию
    company["_lebenslauf_de"] = adapted.get("lebenslauf_de", "")
    company["_anschreiben_de"] = email_data.get("anschreiben_de", "")
    company["_subject"] = email_data.get("email_subject", "")
    selected[idx] = company

    await update_session(session_id,
        selected_companies=json.dumps(selected, ensure_ascii=False),
        step=f"review_{idx}"
    )

    # Показываем документы для проверки
    preview_de = email_data.get("anschreiben_de", "")[:500] + "..."
    preview_user = email_data.get("anschreiben_user", "")[:500] + "..."
    lebenslauf_preview = adapted.get("lebenslauf_de", "")[:300] + "..."

    await websocket.send_json({
        "type": "message",
        "sender": "bot",
        "text": get_message(lang, "review_letter",
            company=company["name"],
            lebenslauf_de=lebenslauf_preview,
            anschreiben_de=preview_de,
            anschreiben_user=preview_user
        ),
        "buttons": (
            ["да", "нет", "поправить"] if lang == "ru" else
            ["yes", "no", "edit"] if lang == "en" else
            ["ja", "nein", "korrigieren"] if lang == "de" else
            ["так", "ні", "виправити"] if lang == "uk" else
            ["نعم", "لا", "تعديل"] if lang == "ar" else
            ["هو", "نه", "سمول"]
        )
    })

async def _next_or_done(websocket, session_id, lang, selected, current_idx):
    next_idx = current_idx + 1
    if next_idx < len(selected):
        await websocket.send_json({
            "type": "message",
            "sender": "bot",
            "text": get_message(lang, "next_company"),
            "buttons": (
                ["да", "нет"] if lang == "ru" else
                ["yes", "no"] if lang == "en" else
                ["ja", "nein"]
            )
        })
        await update_session(session_id, step=f"next_company_{next_idx}")
    else:
        await websocket.send_json({
            "type": "message",
            "sender": "bot",
            "text": get_message(lang, "done", count=len(selected))
        })
        await update_session(session_id, step="done")

# ─────────────────────────────────────────────
# STATIC FILES
# ─────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    with open("static/index.html") as f:
        return HTMLResponse(f.read())
