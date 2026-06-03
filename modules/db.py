import os
import asyncpg
import json
import logging

db_pool = None

async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(os.getenv("DATABASE_URL"))
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id         TEXT PRIMARY KEY,
                lang               TEXT DEFAULT 'ru',
                step               TEXT DEFAULT 'lang',
                cv_text            TEXT,
                cv_profile         JSONB,
                companies          JSONB,
                selected_companies JSONB,
                created_at         TIMESTAMP DEFAULT NOW(),
                updated_at         TIMESTAMP DEFAULT NOW()
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

async def save_sent_email(session_id: str, company_name: str, to_email: str):
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO sent_emails (session_id, company_name, to_email)
            VALUES ($1, $2, $3)
        """, session_id, company_name, to_email)

async def get_pending_followups():
    async with db_pool.acquire() as conn:
        return await conn.fetch("""
            SELECT * FROM sent_emails
            WHERE followup_1 = FALSE
              AND sent_at < NOW() - INTERVAL '3 days'
        """)

async def mark_followup_1(email_id: int):
    async with db_pool.acquire() as conn:
        await conn.execute("""
            UPDATE sent_emails
            SET followup_1 = TRUE, followup_1_at = NOW()
            WHERE id = $1
        """, email_id)

async def mark_followup_2(email_id: int):
    async with db_pool.acquire() as conn:
        await conn.execute("""
            UPDATE sent_emails
            SET followup_2 = TRUE, followup_2_at = NOW()
            WHERE id = $1
        """, email_id)
