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
# АДАПТАЦИЯ CV ПОД КОНКРЕТНУЮ КОМПАНИЮ
# ============================================================
async def adapt_cv(
    profile: dict,
    company: dict,
    job: dict = None,
    lang: str = "ru"
) -> dict:
    """
    Адаптирует профиль кандидата под конкретную компанию/вакансию.
    ATS-оптимизация: правильные ключевые слова, структура, акценты.

    Args:
        profile: профиль из cv_analyst (обогащённый)
        company: {"name": "...", "website": "...", "address": "..."}
        job: {"title": "...", "requirements": "..."} или None (если вакансия не найдена)
        lang: язык кандидата

    Returns:
        adapted_profile с полями для генерации Lebenslauf
    """
    lang_name = LANG_NAMES.get(lang, "русском языке")

    company_name = company.get("name", "")
    company_address = company.get("address", "")
    company_website = company.get("website", "")

    job_title = job.get("title", "") if job else ""
    job_requirements = job.get("requirements", "") if job else ""
    job_match_reason = job.get("match_reason", "") if job else ""

    # Контекст вакансии для промпта
    job_context = ""
    if job_title:
        job_context = f"""
КОНКРЕТНАЯ ВАКАНСИЯ:
- Должность: {job_title}
- Требования: {job_requirements}
- Почему подходит кандидату: {job_match_reason}

Адаптируй CV ТОЧНО под эту вакансию — используй те же ключевые слова что в требованиях.
"""
    else:
        job_context = f"""
Конкретная вакансия не найдена. Адаптируй CV под общий профиль компании {company_name}.
Используй ключевые слова типичные для этой отрасли.
"""

    prompt = f"""Ты — эксперт по ATS-оптимизации резюме для немецкого рынка труда.

ATS (Applicant Tracking System) — это программа которая автоматически отсеивает резюме
до того как их увидит HR. Твоя задача — адаптировать профиль так чтобы ATS его пропустил.

ПРАВИЛА ATS-ОПТИМИЗАЦИИ:
1. Используй ТОЧНЫЕ ключевые слова из требований вакансии (не синонимы)
2. Немецкие компании предпочитают конкретные цифры и достижения
3. Структура: сначала самое релевантное для ЭТОЙ компании
4. Убери или минимизируй нерелевантный опыт
5. Добавь ключевые слова отрасли которых нет в CV но которые подразумеваются

ПРОФИЛЬ КАНДИДАТА:
{json.dumps(profile, ensure_ascii=False, indent=2)}

КОМПАНИЯ:
- Название: {company_name}
- Адрес: {company_address}
- Сайт: {company_website}

{job_context}

Верни JSON без markdown:
{{
  "company_name": "{company_name}",
  "job_title_target": "целевая должность на немецком",
  "professional_summary_de": "Профессиональное резюме 3-4 предложения НА НЕМЕЦКОМ, оптимизированное под эту компанию",
  "professional_summary_candidate_lang": "То же резюме на {lang_name} для кандидата",
  "key_skills_adapted": [
    "навык 1 — сформулирован под требования вакансии",
    "навык 2",
    "навык 3",
    "навык 4",
    "навык 5"
  ],
  "experience_highlights": [
    {{
      "role": "должность",
      "company": "компания",
      "duration": "период",
      "achievements_de": ["достижение 1 с цифрами на немецком", "достижение 2"]
    }}
  ],
  "ats_keywords": [
    "ключевое слово 1 из требований",
    "ключевое слово 2",
    "ключевое слово 3"
  ],
  "cover_letter_angle": "Главный аргумент почему именно этот кандидат подходит именно этой компании (1-2 предложения)",
  "adaptation_notes": "Что было изменено/акцентировано и почему (для кандидата на {lang_name})"
}}"""

    try:
        result = await groq_ask_async(prompt)
        result = clean_json(result)
        adapted = json.loads(result)

        # Добавляем исходные данные компании и вакансии
        adapted["company"] = company
        adapted["job"] = job
        adapted["original_profile"] = {
            "name": profile.get("name", ""),
            "location": profile.get("location", ""),
            "languages": profile.get("languages", []),
            "experience_years": profile.get("experience_years", 0),
        }

        return adapted

    except Exception as e:
        logging.error(f"CV Adapter error: {e}")
        # Fallback — базовая адаптация без LLM
        return {
            "company_name": company_name,
            "job_title_target": job_title or profile.get("cross_domain_opportunities", [""])[0],
            "professional_summary_de": profile.get("summary_de", ""),
            "professional_summary_candidate_lang": "",
            "key_skills_adapted": profile.get("skills", [])[:8],
            "experience_highlights": [],
            "ats_keywords": profile.get("ats_keywords", []),
            "cover_letter_angle": "",
            "adaptation_notes": "Автоматическая адаптация не удалась — используется базовый профиль",
            "company": company,
            "job": job,
            "original_profile": {
                "name": profile.get("name", ""),
                "location": profile.get("location", ""),
                "languages": profile.get("languages", []),
                "experience_years": profile.get("experience_years", 0),
            }
        }


# ============================================================
# АДАПТАЦИЯ ПОД НЕСКОЛЬКО КОМПАНИЙ ПАРАЛЛЕЛЬНО
# ============================================================
async def adapt_cv_for_companies(
    profile: dict,
    companies: list,
    lang: str = "ru"
) -> list:
    """
    Адаптирует CV под список выбранных компаний параллельно.

    Args:
        profile: обогащённый профиль из cv_analyst
        companies: список компаний с вакансиями (из job_search)
        lang: язык кандидата

    Returns:
        Список адаптированных профилей по каждой компании
    """
    semaphore = asyncio.Semaphore(3)  # не более 3 одновременно

    async def adapt_one(company: dict) -> dict:
        async with semaphore:
            # Берём первую наиболее релевантную вакансию (если есть)
            jobs = company.get("jobs", [])
            best_job = None
            if jobs:
                # Сортируем по match_score и берём лучшую
                best_job = max(jobs, key=lambda j: j.get("match_score", 0))

            return await adapt_cv(profile, company, best_job, lang)

    results = await asyncio.gather(
        *[adapt_one(c) for c in companies],
        return_exceptions=True
    )

    adapted_list = []
    for item in results:
        if isinstance(item, dict):
            adapted_list.append(item)

    return adapted_list


# ============================================================
# ФОРМАТИРОВАНИЕ ДЛЯ ПОКАЗА КАНДИДАТУ
# ============================================================
def format_adaptation_message(adapted: dict, lang: str = "ru") -> str:
    """Показывает кандидату что было адаптировано и почему."""

    company_name = adapted.get("company_name", "")
    job_title = adapted.get("job_title_target", "")
    summary = adapted.get("professional_summary_candidate_lang", "")
    skills = adapted.get("key_skills_adapted", [])
    ats_keywords = adapted.get("ats_keywords", [])
    angle = adapted.get("cover_letter_angle", "")
    notes = adapted.get("adaptation_notes", "")

    msg = f"📄 **Резюме адаптировано под: {company_name}**\n"
    if job_title:
        msg += f"🎯 Целевая должность: **{job_title}**\n\n"
    else:
        msg += "\n"

    if summary:
        msg += f"📋 **Ваше профессиональное резюме:**\n{summary}\n\n"

    if skills:
        msg += "🛠️ **Ключевые навыки (адаптированы):**\n"
        for s in skills[:6]:
            msg += f"  • {s}\n"
        msg += "\n"

    if ats_keywords:
        msg += f"🔑 **ATS ключевые слова:** {', '.join(ats_keywords[:8])}\n\n"

    if angle:
        msg += f"💡 **Главный аргумент для письма:**\n{angle}\n\n"

    if notes:
        msg += f"ℹ️ **Что изменено:** {notes}\n"

    return msg