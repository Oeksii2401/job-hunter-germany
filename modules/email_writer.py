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

async def write_email(cv_profile: dict, adapted_cv: dict, company: dict, lang: str = "ru") -> dict:
    """
    Генерирует мотивационное письмо (Anschreiben).
    Возвращает две версии: на немецком и на языке пользователя.
    """
    prompt = f"""Ты — эксперт по деловой переписке для рынка DACH.

ЗАДАЧА: Напиши персонализированное мотивационное письмо (Anschreiben) для кандидата.

ПРАВИЛА:
- Тон: профессиональный, уверенный, без лишней скромности
- Длина: максимум 3 абзаца
- Структура: приветствие → почему я подхожу → почему именно эта компания → призыв к действию
- Письмо должно ДОПОЛНЯТЬ резюме, не копировать его
- Акцентируй международный опыт и LegalTech компетенции если релевантно
- Письмо должно быть живым и конкретным — не шаблонным

ПРОФИЛЬ КАНДИДАТА:
{json.dumps(cv_profile, ensure_ascii=False, indent=2)}

АДАПТИРОВАННОЕ РЕЗЮМЕ (ключевые совпадения):
{json.dumps(adapted_cv.get('key_matches', []), ensure_ascii=False)}

КОМПАНИЯ:
Название: {company.get('name', '')}
Сайт: {company.get('website', '')}
Адрес: {company.get('address', '')}

Отвечай СТРОГО в JSON (без markdown блоков):
{{
  "anschreiben_de": "полный текст письма на немецком",
  "anschreiben_user": "полный текст письма на языке пользователя ({lang})",
  "email_subject": "тема письма на немецком"
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
        logging.error(f"Email Writer error: {e}")
        return {
            "anschreiben_de": "",
            "anschreiben_user": "",
            "email_subject": f"Bewerbung — {cv_profile.get('name', 'Kandidat')}"
        }

async def write_followup(cv_profile: dict, company: dict, followup_number: int, lang: str = "ru") -> dict:
    """Генерирует follow-up письмо (напоминание)."""
    prompt = f"""Ты — эксперт по деловой переписке.

ЗАДАЧА: Напиши краткое follow-up письмо (напоминание о ранее отправленной заявке).

Follow-up номер: {followup_number} ({"3 дня" if followup_number == 1 else "7 дней"} после первого письма)

ПРАВИЛА:
- Очень кратко — максимум 2 абзаца
- Вежливо, без давления
- Напомни о заявке и подтверди интерес
- Профессиональный тон

КАНДИДАТ: {cv_profile.get('name', '')}
КОМПАНИЯ: {company.get('name', '')}

Отвечай СТРОГО в JSON (без markdown блоков):
{{
  "followup_de": "текст письма на немецком",
  "followup_user": "текст письма на языке пользователя ({lang})",
  "email_subject": "тема письма на немецком"
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
        logging.error(f"Follow-up Writer error: {e}")
        return {
            "followup_de": "",
            "followup_user": "",
            "email_subject": f"Nachfrage — Bewerbung {company.get('name', '')}"
        }
