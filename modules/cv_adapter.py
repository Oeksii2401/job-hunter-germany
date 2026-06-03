import os
import json
import logging
import asyncio
from groq import Groq

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
GROQ_MODEL = "llama-3.3-70b-versatile"

def groq_ask(prompt: str) -> str:
    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4000,
    )
    return response.choices[0].message.content

async def groq_ask_async(prompt: str) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, groq_ask, prompt)

async def adapt_cv(cv_text: str, cv_profile: dict, company: dict, lang: str = "ru") -> dict:
    """
    Адаптирует резюме под конкретную компанию.
    Возвращает две версии: на немецком и на языке пользователя.
    """
    prompt = f"""Ты — эксперт по составлению резюме для рынка DACH.

ЗАДАЧА: Адаптируй резюме под конкретную компанию для прохождения ATS-фильтров.

ПРАВИЛА:
- Выдели навыки максимально совпадающие с профилем компании
- Добавь ключевые слова характерные для отрасли на немецком
- НЕ выдумывай опыт — только перефразируй и выделяй реальный
- Структура Lebenslauf: Profil → Berufserfahrung → Kenntnisse → Sprachen
- Учти что кандидат юрист НЕ немецкого права — акцентируй международный опыт и LegalTech компетенции

ПРОФИЛЬ КАНДИДАТА:
{json.dumps(cv_profile, ensure_ascii=False, indent=2)}

КОМПАНИЯ:
Название: {company.get('name', '')}
Сайт: {company.get('website', '')}
Адрес: {company.get('address', '')}

ОРИГИНАЛЬНОЕ РЕЗЮМЕ:
{cv_text}

Отвечай СТРОГО в JSON (без markdown блоков):
{{
  "lebenslauf_de": "полный текст резюме на немецком",
  "lebenslauf_user": "полный текст резюме на языке пользователя ({lang})",
  "key_matches": ["ключевое совпадение 1", "ключевое совпадение 2"],
  "ats_keywords": ["ключевое слово ATS 1", "ключевое слово ATS 2"]
}}"""

    try:
        result = await groq_ask_async(prompt)
        result = result.strip()
        if result.startswith("```"):
            result = result.split("```")[1]
            if result.startswith("json"):
                result = result[4:]
        return json.loads(result.strip())
    except Exception as e:
        logging.error(f"CV Adapter error: {e}")
        return {
            "lebenslauf_de": cv_text,
            "lebenslauf_user": cv_text,
            "key_matches": [],
            "ats_keywords": []
        }
