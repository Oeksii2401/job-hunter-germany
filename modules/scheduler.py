import os
import logging
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()


async def check_followups(db_pool, bot_send_func):
    """
    Проверяет отправленные письма и запускает follow-up если нужно.
    Запускается каждый час.

    Follow-up 1 — через 3 дня после отправки письма
    Follow-up 2 — через 7 дней после follow-up 1 (не после sent_at)
    """
    try:
        async with db_pool.acquire() as conn:

            # ── Follow-up 1 — через 3 дня после sent_at ──────────────────
            pending_1 = await conn.fetch("""
                SELECT * FROM sent_emails
                WHERE followup_1 = FALSE
                  AND sent_at < NOW() - INTERVAL '3 days'
            """)

            for row in pending_1:
                try:
                    await bot_send_func(
                        session_id=row['session_id'],
                        event="followup_1",
                        data=dict(row)
                    )
                    await conn.execute("""
                        UPDATE sent_emails
                        SET followup_1 = TRUE, followup_1_at = NOW()
                        WHERE id = $1
                    """, row['id'])
                    logging.info(f"Follow-up 1 sent: {row['company_name']} (session {row['session_id']})")
                except Exception as e:
                    logging.error(f"Follow-up 1 error for {row.get('company_name')}: {e}")

            # ── Follow-up 2 — через 7 дней после followup_1_at ───────────
            # ВАЖНО: отсчёт от followup_1_at, не от sent_at
            pending_2 = await conn.fetch("""
                SELECT * FROM sent_emails
                WHERE followup_2 = FALSE
                  AND followup_1 = TRUE
                  AND followup_1_at IS NOT NULL
                  AND followup_1_at < NOW() - INTERVAL '7 days'
            """)

            for row in pending_2:
                try:
                    await bot_send_func(
                        session_id=row['session_id'],
                        event="followup_2",
                        data=dict(row)
                    )
                    await conn.execute("""
                        UPDATE sent_emails
                        SET followup_2 = TRUE, followup_2_at = NOW()
                        WHERE id = $1
                    """, row['id'])
                    logging.info(f"Follow-up 2 sent: {row['company_name']} (session {row['session_id']})")
                except Exception as e:
                    logging.error(f"Follow-up 2 error for {row.get('company_name')}: {e}")

    except Exception as e:
        logging.error(f"Scheduler check_followups error: {e}")


def start_scheduler(db_pool, bot_send_func):
    """Запускает планировщик follow-up писем."""
    scheduler.add_job(
        check_followups,
        'interval',
        hours=1,
        args=[db_pool, bot_send_func],
        id='followup_checker',
        replace_existing=True
    )
    scheduler.start()
    logging.info("Scheduler started — checking follow-ups every hour")


def stop_scheduler():
    """Останавливает планировщик."""
    if scheduler.running:
        scheduler.shutdown()
        logging.info("Scheduler stopped")