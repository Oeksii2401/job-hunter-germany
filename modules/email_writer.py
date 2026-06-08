import os
import json
import logging
import asyncio
import re
from groq import Groq

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
GROQ_MODEL = "llama-3.3-70b-versatile"

LANG_NAMES = {
    "ru": "русском языке",
    "de": "deutscher Sprache",
    "en": "English",
    "uk": "українській мові",
    "ar": "اللغة العربية",
    "ps": "پښتو ژبه"
}


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================
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


def clean_json(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


# ============================================================
# ГЕНЕРАЦИЯ МОТИВАЦИОННОГО ПИСЬМА
# ============================================================
async def write_email(
    cv_profile: dict,
    adapted_cv: dict,
    company: dict,
    lang: str = "ru"
) -> dict:
    """
    Генерирует мотивационное письмо (Anschreiben).

    Использует данные из adapted_cv:
    - cover_letter_angle — главный аргумент
    - ats_keywords — ключевые слова для ATS
    - professional_summary_de — резюме на немецком
    - job_title_target — целевая должность

    Возвращает две версии: на немецком и на языке кандидата.
    """
    lang_name = LANG_NAMES.get(lang, "русском языке")

    candidate_name = cv_profile.get("name", "")
    candidate_location = cv_profile.get("location", "")
    experience_years = cv_profile.get("experience_years", 0)
    skills = cv_profile.get("skills", [])
    languages = cv_profile.get("languages", [])

    company_name = company.get("name", "")
    company_address = company.get("address", "")
    company_website = company.get("website", "")

    # Данные из адаптированного CV
    job_title = adapted_cv.get("job_title_target", "")
    cover_angle = adapted_cv.get("cover_letter_angle", "")
    ats_keywords = adapted_cv.get("ats_keywords", [])
    summary_de = adapted_cv.get("professional_summary_de", "")
    key_skills = adapted_cv.get("key_skills_adapted", skills[:6])

    # Данные о вакансии если есть
    job = adapted_cv.get("job") or {}
    job_title_from_search = job.get("title", "") if job else ""
    job_requirements = job.get("requirements", "") if job else ""

    final_job_title = job_title_from_search or job_title

    prompt = f"""Ты — эксперт по деловой переписке для рынка DACH (Германия, Австрия, Швейцария).
Ты знаешь немецкую деловую культуру изнутри и умеешь писать письма которые проходят ATS-фильтры.

═══════════════════════════════════════
ПРОФИЛЬ КАНДИДАТА:
- Имя: {candidate_name}
- Локация: {candidate_location}
- Опыт: {experience_years} лет
- Навыки: {', '.join(skills[:8])}
- Языки: {json.dumps(languages, ensure_ascii=False)}

КОМПАНИЯ:
- Название: {company_name}
- Адрес: {company_address}
- Сайт: {company_website}

ЦЕЛЕВАЯ ДОЛЖНОСТЬ: {final_job_title}
ТРЕБОВАНИЯ ВАКАНСИИ: {job_requirements}

ДАННЫЕ ИЗ АДАПТАЦИИ:
- Главный аргумент: {cover_angle}
- ATS ключевые слова: {', '.join(ats_keywords)}
- Профессиональное резюме (DE): {summary_de}
- Адаптированные навыки: {', '.join(key_skills[:6])}

═══════════════════════════════════════
ПРАВИЛА НЕМЕЦКОГО ANSCHREIBEN:

1. СТРУКТУРА (строго):
   - Ort, Datum (город и дата) — справа вверху
   - Empfänger (получатель) — слева
   - Betreff (тема) — жирным
   - Anrede (приветствие) — "Sehr geehrte Damen und Herren," или имя если известно
   - Einleitung (1 абзац) — зачем пишу, что привлекло в компании
   - Hauptteil (1-2 абзаца) — почему я подхожу, конкретные достижения с цифрами
   - Schluss (1 абзац) — призыв к действию, готовность к встрече
   - Grußformel — "Mit freundlichen Grüßen"
   - Unterschrift

2. НЕМЕЦКИЙ СТИЛЬ:
   - Конкретность и факты — никаких абстракций
   - Цифры и результаты везде где можно
   - Не хвастовство, а факты
   - Формальный но не сухой тон

3. ATS-ОПТИМИЗАЦИЯ:
   - Включи ключевые слова: {', '.join(ats_keywords[:5])}
   - Используй ТОЧНЫЕ формулировки из требований вакансии
   - Не заменяй ключевые слова синонимами

4. ЗАПРЕЩЕНО:
   - Шаблонные фразы типа "Hiermit bewerbe ich mich..."
   - Копирование текста резюме
   - Лишняя скромность
   - Письмо длиннее одной страницы A4

═══════════════════════════════════════
Отвечай СТРОГО в JSON без markdown:
{{
  "anschreiben_de": "полный текст письма на немецком со всеми элементами структуры",
  "anschreiben_user": "полный текст письма на {lang_name} — качественный перевод с сохранением смысла",
  "email_subject": "тема письма на немецком (кратко: Bewerbung als [должность] — [имя])",
  "email_subject_display": "тема письма на {lang_name} для показа кандидату"
}}"""

    try:
        result = await groq_ask_async(prompt)
        result = clean_json(result)
        email_data = json.loads(result)

        # Добавляем метаданные
        email_data["company_name"] = company_name
        email_data["candidate_name"] = candidate_name
        email_data["job_title"] = final_job_title
        email_data["to_email"] = company.get("email", "")

        return email_data

    except Exception as e:
        logging.error(f"Email Writer error: {e}")
        return {
            "anschreiben_de": "",
            "anschreiben_user": "",
            "email_subject": f"Bewerbung — {candidate_name}",
            "email_subject_display": f"Заявка — {company_name}",
            "company_name": company_name,
            "candidate_name": candidate_name,
            "job_title": final_job_title,
            "to_email": company.get("email", "")
        }


# ============================================================
# ГЕНЕРАЦИЯ FOLLOW-UP ПИСЬМА
# ============================================================
async def write_followup(
    cv_profile: dict,
    company: dict,
    followup_number: int,
    lang: str = "ru"
) -> dict:
    """
    Генерирует follow-up письмо (напоминание о заявке).

    Args:
        cv_profile: профиль кандидата
        company: данные компании
        followup_number: 1 (через 3 дня) или 2 (через 7 дней)
        lang: язык кандидата
    """
    lang_name = LANG_NAMES.get(lang, "русском языке")

    candidate_name = cv_profile.get("name", "")
    company_name = company.get("name", "")
    days = "3 дня" if followup_number == 1 else "7 дней"
    days_de = "3 Tagen" if followup_number == 1 else "einer Woche"

    prompt = f"""Ты — эксперт по деловой переписке для немецкого рынка.

ЗАДАЧА: Напиши краткое follow-up письмо — вежливое напоминание о заявке.

КОНТЕКСТ:
- Кандидат: {candidate_name}
- Компания: {company_name}
- Прошло времени с момента отправки заявки: {days} ({days_de})
- Follow-up номер: {followup_number}

ПРАВИЛА:
- Максимум 2 коротких абзаца
- Вежливо и уверенно — без давления и извинений
- Напомни о заявке одной фразой
- Подтверди интерес и готовность к встрече
- Немецкий деловой стиль

Отвечай СТРОГО в JSON без markdown:
{{
  "followup_de": "текст письма на немецком",
  "followup_user": "текст письма на {lang_name}",
  "email_subject": "тема на немецком (Nachfrage: Bewerbung als [должность])"
}}"""

    try:
        result = await groq_ask_async(prompt)
        result = clean_json(result)
        return json.loads(result)

    except Exception as e:
        logging.error(f"Follow-up Writer error: {e}")
        return {
            "followup_de": "",
            "followup_user": "",
            "email_subject": f"Nachfrage — Bewerbung {company_name}"
        }


# ============================================================
# ФОРМАТИРОВАНИЕ ПИСЬМА ДЛЯ ПРОСМОТРА КАНДИДАТОМ
# ============================================================
def format_email_preview(email_data: dict, lang: str = "ru") -> str:
    """Показывает кандидату письмо для проверки перед отправкой."""

    company_name = email_data.get("company_name", "")
    job_title = email_data.get("job_title", "")
    subject = email_data.get("email_subject_display") or email_data.get("email_subject", "")
    letter_user = email_data.get("anschreiben_user", "")
    letter_de = email_data.get("anschreiben_de", "")

    msg = f"✉️ **Письмо для: {company_name}**\n"
    if job_title:
        msg += f"🎯 Должность: {job_title}\n"
    msg += f"📌 Тема: {subject}\n\n"

    if letter_user:
        msg += f"**Текст письма (ваш язык):**\n{letter_user}\n\n"
        msg += "---\n\n"

    if letter_de:
        msg += f"**Текст письма (немецкий — именно это будет отправлено):**\n{letter_de}\n\n"

    msg += "✏️ Хотите что-то изменить или отправляем?"

    return msg