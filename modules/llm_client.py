import os
import re
import json
import time
import asyncio
import logging
from groq import Groq

GROQ_MODEL = "openai/gpt-oss-120b"
GEMINI_MODEL = "gemini-2.5-flash"

# max_retries=0 — отключаем встроенные повторы Groq SDK (по умолчанию делает
# несколько retry с задержками до 20+ сек), чтобы наш fallback на Gemini
# срабатывал сразу при 429, а не после долгого внутреннего ожидания
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"), max_retries=0)

_gemini_client = None


def _get_gemini_client():
    """Ленивая инициализация Gemini — не падаем при импорте, если ключа нет."""
    global _gemini_client
    if _gemini_client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return None
        from google import genai
        _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client


def _is_rate_limit_error(e: Exception) -> bool:
    msg = str(e).lower()
    return "429" in msg or "rate_limit" in msg or "rate limit" in msg


def _groq_ask(prompt: str, max_tokens: int = 4000) -> str:
    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content


def _gemini_ask(prompt: str) -> str:
    client = _get_gemini_client()
    if client is None:
        raise RuntimeError("GEMINI_API_KEY не задан — fallback недоступен")
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
    )
    return response.text


def ask(prompt: str, max_tokens: int = 4000) -> str:
    """Синхронный вызов LLM. Groq — основной провайдер.
    При превышении лимита (429 / rate limit) автоматически переключается на Gemini."""
    try:
        return _groq_ask(prompt, max_tokens=max_tokens)
    except Exception as e:
        if _is_rate_limit_error(e):
            logging.warning(f"Groq rate limit, переключаюсь на Gemini: {e}")
            try:
                return _gemini_ask(prompt)
            except Exception as e2:
                logging.warning(f"Gemini fallback не сработал с первой попытки, retry через 2с: {e2}")
                time.sleep(2)
                try:
                    return _gemini_ask(prompt)
                except Exception as e3:
                    logging.error(f"Gemini fallback не сработал и со второй попытки: {e3}")
                    raise
        raise


async def ask_async(prompt: str, max_tokens: int = 4000) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: ask(prompt, max_tokens))


def clean_json(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()
