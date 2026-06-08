import os
import uuid
import json
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from modules.db import init_db, get_session, update_session, save_sent_email
from modules.cv_parser import parse_cv, extract_pdf_text, is_full_cv
from modules.cv_analyst import analyze_profile, format_analyst_report
from modules.job_search import find_companies_for_profile
from modules.cv_adapter import adapt_cv
from modules.email_writer import write_email, write_followup
from modules.email_sender import send_application, send_followup
from modules.scheduler import start_scheduler, stop_scheduler
from prompts.prompts import get_message

logging.basicConfig(level=logging.INFO)

app = FastAPI()

active_connections: dict = {}


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
# ВОПРОСЫ ДЛЯ СБОРА ДАННЫХ (если нет резюме)
# ─────────────────────────────────────────────
COLLECT_INFO_QUESTIONS = {
    "name": {
        "ru": "👤 Как вас зовут? (Имя и фамилия)",
        "de": "👤 Wie heißen Sie? (Vor- und Nachname)",
        "en": "👤 What is your name? (First and last name)",
        "uk": "👤 Як вас звати? (Ім'я та прізвище)",
        "ar": "👤 ما اسمك؟ (الاسم الأول والأخير)",
        "ps": "👤 ستاسو نوم څه دی؟",
    },
    "profession": {
        "ru": "💼 Какова ваша профессия и специализация?",
        "de": "💼 Was ist Ihr Beruf und Ihre Spezialisierung?",
        "en": "💼 What is your profession and specialization?",
        "uk": "💼 Яка ваша професія та спеціалізація?",
        "ar": "💼 ما هي مهنتك وتخصصك؟",
        "ps": "💼 ستاسو مسلک او تخصص څه دی؟",
    },
    "experience": {
        "ru": "📅 Сколько лет опыта работы у вас есть? Кратко опишите последние 2-3 места работы.",
        "de": "📅 Wie viele Jahre Berufserfahrung haben Sie? Beschreiben Sie kurz Ihre letzten 2-3 Arbeitsstellen.",
        "en": "📅 How many years of experience do you have? Briefly describe your last 2-3 jobs.",
        "uk": "📅 Скільки років досвіду роботи у вас є? Коротко опишіть останні 2-3 місця роботи.",
        "ar": "📅 كم سنة من الخبرة لديك؟ صف بإيجاز آخر 2-3 وظائف.",
        "ps": "📅 تاسو څومره کاري تجربه لرئ؟ وروستي 2-3 دندې لنډ بیان کړئ.",
    },
    "skills": {
        "ru": "🛠 Перечислите ваши ключевые навыки (технические и soft skills):",
        "de": "🛠 Listen Sie Ihre wichtigsten Fähigkeiten auf (technische und Soft Skills):",
        "en": "🛠 List your key skills (technical and soft skills):",
        "uk": "🛠 Перелічіть ваші ключові навички (технічні та soft skills):",
        "ar": "🛠 اذكر مهاراتك الرئيسية (التقنية والشخصية):",
        "ps": "🛠 خپل مهم مهارتونه ولیکئ:",
    },
    "languages": {
        "ru": "🌍 Какими языками вы владеете и на каком уровне? (например: Немецкий B1, Английский C1)",
        "de": "🌍 Welche Sprachen sprechen Sie und auf welchem Niveau? (z.B.: Deutsch B1, Englisch C1)",
        "en": "🌍 What languages do you speak and at what level? (e.g.: German B1, English C1)",
        "uk": "🌍 Якими мовами ви володієте і на якому рівні? (наприклад: Німецька B1, Англійська C1)",
        "ar": "🌍 ما اللغات التي تتحدثها وما مستواك؟",
        "ps": "🌍 کوم ژبې پوهیږئ او کوم کچه؟",
    },
    "email": {
        "ru": "📧 Укажите ваш email для связи:",
        "de": "📧 Geben Sie Ihre E-Mail-Adresse an:",
        "en": "📧 Please provide your email address:",
        "uk": "📧 Вкажіть ваш email для зв'язку:",
        "ar": "📧 أدخل بريدك الإلكتروني:",
        "ps": "📧 خپل بریښنالیک وولیکئ:",
    },
}

COLLECT_INFO_ORDER = ["name", "profession", "experience", "skills", "languages", "email"]


def get_collect_question(field: str, lang: str) -> str:
    return COLLECT_INFO_QUESTIONS.get(field, {}).get(lang, COLLECT_INFO_QUESTIONS[field]["ru"])


def build_cv_from_collected(collected: dict) -> str:
    """Собирает текст резюме из ответов пользователя."""
    return f"""
Имя: {collected.get('name', '')}
Профессия: {collected.get('profession', '')}
Опыт работы: {collected.get('experience', '')}
Навыки: {collected.get('skills', '')}
Языки: {collected.get('languages', '')}
Email: {collected.get('email', '')}
""".strip()


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    active_connections[session_id] = websocket
    logging.info(f"WS connected: {session_id}")

    session = await get_session(session_id)
    lang = session.get("lang", "ru")

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

                upload_prompts = {
                    "ru": "Отлично! Загрузи резюме в PDF или вставь текст.\n\nЕсли резюме нет — просто напиши свою профессию, и я помогу собрать профиль.",
                    "de": "Super! Lade deinen Lebenslauf als PDF hoch oder füge den Text ein.\n\nOhne Lebenslauf — schreib einfach deinen Beruf, ich helfe dir ein Profil zu erstellen.",
                    "en": "Great! Upload your CV as PDF or paste the text.\n\nNo CV? Just write your profession and I'll help build your profile.",
                    "uk": "Чудово! Завантаж резюме у PDF або встав текст.\n\nЯкщо немає резюме — просто напиши свою професію.",
                    "ar": "رائع! حمّل سيرتك الذاتية PDF أو الصق النص.\n\nبدون سيرة ذاتية؟ اكتب مهنتك فقط.",
                    "ps": "ښه! خپل CV د PDF په توګه آپلوډ کړئ یا متن پیسټ کړئ.\n\nCV نشته؟ خپل مسلک ولیکئ.",
                }
                await websocket.send_json({
                    "type": "message",
                    "sender": "bot",
                    "text": upload_prompts.get(lang, upload_prompts["ru"]),
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

                if is_full_cv(cv_text):
                    await update_session(session_id, cv_text=cv_text, step="parsing")
                    await websocket.send_json({
                        "type": "message",
                        "sender": "bot",
                        "text": get_message(lang, "parsing")
                    })
                    profile = await parse_cv(cv_text, lang)
                    await _after_parsing(websocket, session_id, lang, profile)
                else:
                    collected = {"profession": cv_text}
                    await update_session(session_id,
                        cv_text=cv_text,
                        step="collect_info",
                        cv_profile=json.dumps({"_collected": collected, "_collect_index": 0}, ensure_ascii=False)
                    )
                    await websocket.send_json({
                        "type": "message",
                        "sender": "bot",
                        "text": get_collect_question("name", lang)
                    })

            # ── Сбор данных по одному ─────────────────
            elif step == "collect_info":
                profile_data = json.loads(session.get("cv_profile") or "{}")
                collected = profile_data.get("_collected", {})
                collect_index = profile_data.get("_collect_index", 0)

                fields_to_ask = [f for f in COLLECT_INFO_ORDER if f != "profession"]
                current_field = fields_to_ask[collect_index] if collect_index < len(fields_to_ask) else None

                if current_field:
                    collected[current_field] = text
                    collect_index += 1

                profile_data["_collected"] = collected
                profile_data["_collect_index"] = collect_index
                await update_session(session_id, cv_profile=json.dumps(profile_data, ensure_ascii=False))

                fields_to_ask = [f for f in COLLECT_INFO_ORDER if f != "profession"]
                if collect_index < len(fields_to_ask):
                    next_field = fields_to_ask[collect_index]
                    await websocket.send_json({
                        "type": "message",
                        "sender": "bot",
                        "text": get_collect_question(next_field, lang)
                    })
                else:
                    cv_text = build_cv_from_collected(collected)
                    await update_session(session_id, cv_text=cv_text, step="parsing")

                    name = collected.get("name", "")
                    greeting = {
                        "ru": f"Отлично, {name}! Анализирую ваш профиль...",
                        "de": f"Sehr gut, {name}! Ich analysiere Ihr Profil...",
                        "en": f"Great, {name}! Analyzing your profile...",
                        "uk": f"Чудово, {name}! Аналізую ваш профіль...",
                        "ar": f"رائع، {name}! أحلل ملفك الشخصي...",
                        "ps": f"ښه، {name}! ستاسو پروفایل تحلیلوم...",
                    }
                    await websocket.send_json({
                        "type": "message",
                        "sender": "bot",
                        "text": greeting.get(lang, greeting["ru"])
                    })

                    profile = await parse_cv(cv_text, lang)
                    profile["email"] = collected.get("email", "")
                    await _after_parsing(websocket, session_id, lang, profile)

            # ── Уточняющие вопросы ────────────────────
            elif step == "questions":
                profile = json.loads(session.get("cv_profile") or "{}")
                questions = profile.get("clarifying_questions", [])
                q_index = profile.get("_q_index", 0)

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
                    # ── Все вопросы собраны → запускаем cv_analyst ──
                    await websocket.send_json({
                        "type": "message",
                        "sender": "bot",
                        "text": get_message(lang, "analyzing")
                    })

                    qa_pairs = [
                        {"question": a["q"], "answer": a["a"]}
                        for a in profile.get("_answers", [])
                    ]

                    enriched = await analyze_profile(profile, qa_pairs, lang)

                    # Показываем отчёт аналитика
                    report_text = format_analyst_report(enriched, lang)
                    if report_text:
                        await websocket.send_json({
                            "type": "message",
                            "sender": "bot",
                            "text": report_text
                        })

                    await _ask_location(websocket, session_id, lang, enriched)

            # ── Выбор локации ─────────────────────────
            elif step == "ask_location":
                profile = json.loads(session.get("cv_profile") or "{}")
                profile["location"] = text
                await update_session(session_id,
                    cv_profile=json.dumps(profile, ensure_ascii=False),
                    step="job_search"
                )
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
async def _after_parsing(websocket, session_id, lang, profile):
    """Вызывается после парсинга CV — показывает результат и задаёт вопросы."""
    profile_json = json.dumps(profile, ensure_ascii=False)
    await update_session(session_id, cv_profile=profile_json, step="questions")

    name = profile.get("name", "")
    hidden = ", ".join(profile.get("hidden_competencies", [])[:2])
    opportunities = ", ".join(profile.get("cross_domain_opportunities", [])[:2])

    if name:
        name_greetings = {
            "ru": f"Приятно познакомиться, {name}! Вот что я нашёл в вашем профиле:",
            "de": f"Schön Sie kennenzulernen, {name}! Das habe ich in Ihrem Profil gefunden:",
            "en": f"Nice to meet you, {name}! Here's what I found in your profile:",
            "uk": f"Приємно познайомитися, {name}! Ось що я знайшов у вашому профілі:",
            "ar": f"سعيد بلقائك، {name}! إليك ما وجدته في ملفك:",
            "ps": f"ستاسو سره د لیدو خوشالي وکړه، {name}! ستاسو پروفایل کې مې دا وموندل:",
        }
        intro = name_greetings.get(lang, name_greetings["ru"])
    else:
        intro = get_message(lang, "parsed_ok",
            domain=profile.get("primary_domain", ""),
            hidden=hidden or "—",
            opportunities=opportunities or "—"
        )

    await websocket.send_json({
        "type": "message",
        "sender": "bot",
        "text": intro
    })

    if name:
        await websocket.send_json({
            "type": "message",
            "sender": "bot",
            "text": get_message(lang, "parsed_ok",
                domain=profile.get("primary_domain", ""),
                hidden=hidden or "—",
                opportunities=opportunities or "—"
            )
        })

    questions = profile.get("clarifying_questions", [])
    if questions:
        await update_session(session_id,
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
        # Нет вопросов — сразу аналитик с пустым диалогом
        enriched = await analyze_profile(profile, [], lang)
        await _ask_location(websocket, session_id, lang, enriched)


async def _ask_location(websocket, session_id, lang, profile):
    location_from_cv = profile.get("location", "")

    # Сохраняем обогащённый профиль перед переходом к локации
    await update_session(session_id,
        cv_profile=json.dumps(profile, ensure_ascii=False),
        step="ask_location"
    )

    location_prompts = {
        "ru": f"📍 Где вы ищете работу?\n\nВ резюме указано: {location_from_cv or 'не указано'}\n\nПодтвердите город или введите другой:",
        "de": f"📍 Wo suchen Sie Arbeit?\n\nIm Lebenslauf: {location_from_cv or 'nicht angegeben'}\n\nBestätigen Sie die Stadt oder geben Sie eine andere ein:",
        "en": f"📍 Where are you looking for work?\n\nYour CV shows: {location_from_cv or 'not specified'}\n\nConfirm the city or enter another:",
        "uk": f"📍 Де ви шукаєте роботу?\n\nУ резюме: {location_from_cv or 'не вказано'}\n\nПідтвердіть місто або введіть інше:",
        "ar": f"📍 أين تبحث عن عمل؟\n\nفي السيرة الذاتية: {location_from_cv or 'غير محدد'}\n\nأكد المدينة أو أدخل أخرى:",
        "ps": f"📍 چیرته کار لټوئ؟\n\nCV کې: {location_from_cv or 'نه دی ټاکل شوی'}\n\nښار تایید کړئ یا بل دننه کړئ:",
    }

    buttons = []
    if location_from_cv:
        buttons.append(location_from_cv)
    buttons.extend(["Berlin", "München", "Hamburg", "Frankfurt", "Hannover"])

    await websocket.send_json({
        "type": "message",
        "sender": "bot",
        "text": location_prompts.get(lang, location_prompts["ru"]),
        "buttons": buttons
    })


async def _do_job_search(websocket, session_id, lang, profile):
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
    profile = json.loads(session.get("cv_profile") or "{}")

    await websocket.send_json({
        "type": "message",
        "sender": "bot",
        "text": get_message(lang, "adapting", company=company["name"])
    })

    # Новая сигнатура: adapt_cv(profile, company, job, lang)
    best_job = None
    jobs = company.get("jobs", [])
    if jobs:
        best_job = max(jobs, key=lambda j: j.get("match_score", 0))

    adapted = await adapt_cv(profile, company, best_job, lang)

    await websocket.send_json({
        "type": "message",
        "sender": "bot",
        "text": get_message(lang, "writing_email", company=company["name"])
    })

    email_data = await write_email(profile, adapted, company, lang)

    # Сохраняем данные письма в компанию
    company["_lebenslauf_de"] = adapted.get("professional_summary_de", "")
    company["_anschreiben_de"] = email_data.get("anschreiben_de", "")
    company["_subject"] = email_data.get("email_subject", "")
    selected[idx] = company

    await update_session(session_id,
        selected_companies=json.dumps(selected, ensure_ascii=False),
        step=f"review_{idx}"
    )

    preview_de = email_data.get("anschreiben_de", "")[:500] + "..."
    preview_user = email_data.get("anschreiben_user", "")[:500] + "..."
    lebenslauf_preview = adapted.get("professional_summary_de", "")[:300] + "..."

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