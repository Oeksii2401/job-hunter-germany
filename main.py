import os
import uuid
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import asyncpg
import asyncio
import logging

logging.basicConfig(level=logging.INFO)

app = FastAPI()

# ─────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────
db_pool = None

async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(os.getenv("DATABASE_URL"))
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id       TEXT PRIMARY KEY,
                lang             TEXT DEFAULT 'ru',
                step             TEXT DEFAULT 'lang',
                cv_text          TEXT,
                cv_profile       JSONB,
                companies        JSONB,
                selected_companies JSONB,
                created_at       TIMESTAMP DEFAULT NOW(),
                updated_at       TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS sent_emails (
                id            SERIAL PRIMARY KEY,
                session_id    TEXT,
                company_name  TEXT,
                to_email      TEXT,
                sent_at       TIMESTAMP DEFAULT NOW(),
                followup_1    BOOLEAN DEFAULT FALSE,
                followup_2    BOOLEAN DEFAULT FALSE,
                followup_1_at TIMESTAMP,
                followup_2_at TIMESTAMP
            )
        """)
    logging.info("DB ready")

async def get_session(session_id: str) -> dict:
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM sessions WHERE session_id=$1", session_id
        )
        if not row:
            await conn.execute(
                "INSERT INTO sessions (session_id) VALUES ($1)", session_id
            )
            row = await conn.fetchrow(
                "SELECT * FROM sessions WHERE session_id=$1", session_id
            )
        return dict(row)

async def update_session(session_id: str, **kwargs):
    if not kwargs:
        return
    sets = ", ".join(f"{k}=${i+2}" for i, k in enumerate(kwargs))
    vals = list(kwargs.values())
    async with db_pool.acquire() as conn:
        await conn.execute(
            f"UPDATE sessions SET {sets}, updated_at=NOW() WHERE session_id=$1",
            session_id, *vals
        )

# ─────────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    await init_db()
    logging.info("App started")

# ─────────────────────────────────────────────
# WEBSOCKET
# ─────────────────────────────────────────────
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    logging.info(f"WS connected: {session_id}")
    
    session = await get_session(session_id)
    
    # Приветствие
    await websocket.send_json({
        "type": "message",
        "sender": "bot",
        "text": "👋 Привет! Я — Job Hunter Germany. Помогу найти работу в DACH регионе.\n\nВыбери язык:",
        "buttons": ["🇷🇺 Русский", "🇩🇪 Deutsch", "🇬🇧 English", "🇺🇦 Українська", "🇸🇦 العربية", "🇦🇫 پښتو"]
    })
    
    try:
        while True:
            data = await websocket.receive_json()
            session = await get_session(session_id)
            step = session.get("step", "lang")
            
            msg_type = data.get("type", "text")
            text = data.get("text", "")
            
            # ── Выбор языка ──────────────────
            if step == "lang":
                lang_map = {
                    "🇷🇺 Русский":    "ru",
                    "🇩🇪 Deutsch":    "de",
                    "🇬🇧 English":    "en",
                    "🇺🇦 Українська": "uk",
                    "🇸🇦 العربية":    "ar",
                    "🇦🇫 پښتو":       "ps",
                }
                lang = lang_map.get(text, "ru")
                await update_session(session_id, lang=lang, step="upload_cv")
                
                greetings = {
                    "ru": "Отлично! Теперь загрузи своё резюме в формате PDF или вставь текст прямо сюда.",
                    "de": "Super! Lade nun deinen Lebenslauf als PDF hoch oder füge den Text hier ein.",
                    "en": "Great! Now upload your CV as PDF or paste the text here.",
                    "uk": "Чудово! Тепер завантаж своє резюме у форматі PDF або вставте текст сюди.",
                    "ar": "رائع! الآن قم بتحميل سيرتك الذاتية بصيغة PDF أو الصق النص هنا.",
                    "ps": "ښه! اوس خپل CV د PDF په توګه آپلوډ کړئ یا متن دلته پیسټ کړئ.",
                }
                await websocket.send_json({
                    "type": "message",
                    "sender": "bot",
                    "text": greetings.get(lang, greetings["ru"]),
                    "show_upload": True
                })
                continue
            
            # ── Загрузка CV (текст) ──────────
            if step == "upload_cv":
                if text:
                    await update_session(session_id, cv_text=text, step="parsing")
                    await websocket.send_json({
                        "type": "message",
                        "sender": "bot",
                        "text": "⏳ Анализирую резюме..."
                    })
                    # TODO: вызов CV_Parser
                    await update_session(session_id, step="questions")
                    await websocket.send_json({
                        "type": "message",
                        "sender": "bot",
                        "text": "✅ Резюме получено! CV_Parser будет подключён на следующем шаге."
                    })
                continue
            
            # ── Заглушка для остальных шагов ─
            await websocket.send_json({
                "type": "message",
                "sender": "bot",
                "text": f"Шаг: {step}. В разработке..."
            })
    
    except WebSocketDisconnect:
        logging.info(f"WS disconnected: {session_id}")

# ─────────────────────────────────────────────
# STATIC FILES
# ─────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    with open("static/index.html") as f:
        return HTMLResponse(f.read())
