import os
import json
import logging
import asyncio
import re
from modules.llm_client import ask_async as groq_ask_async, clean_json
LANG_NAMES = {
    "ru": "русском языке",
    "de": "deutscher Sprache",
    "en": "English",
    "uk": "українській мові",
    "ar": "اللغة العربية",
    "ps": "پښتو ژبه"
}

# ============================================================
# КРИТИЧЕСКИЕ ATS-ФИЛЬТРЫ
# ============================================================
ATS_CRITICAL_FILTERS = {
    "language_german": {
        "triggers": ["deutsch", "german", "deutschkenntnisse", "sprachkenntnisse",
                     "c1", "c2", "b2", "fließend", "verhandlungssicher", "muttersprache"],
        "description": "Требование немецкого языка",
        "fix": "Указать РЕАЛЬНЫЙ уровень кандидата из профиля (например 'Deutsch: A2' или 'Deutsch: Grundkenntnisse') — НЕ завышать",
        "ats_format": "Deutsch: [уровень] — в разделе Sprachkenntnisse"
    },
    "language_english": {
        "triggers": ["english", "englisch", "englischkenntnisse"],
        "description": "Требование английского языка",
        "fix": "Указать РЕАЛЬНЫЙ уровень кандидата из профиля (например 'Englisch: Grundkenntnisse') — НЕ завышать",
        "ats_format": "Englisch: [уровень]"
    },
    "work_permit": {
        "triggers": ["arbeitserlaubnis", "work permit", "visa", "eu-bürger",
                     "aufenthaltstitel", "berechtigung"],
        "description": "Требование разрешения на работу",
        "fix": "Явно: 'EU-Bürger', 'Arbeitserlaubnis vorhanden' или 'Blaue Karte'",
        "ats_format": "Arbeitsgenehmigung: [статус]"
    },
    "education_degree": {
        "triggers": ["bachelor", "master", "studium", "hochschulabschluss",
                     "universitätsabschluss", "abschluss", "degree"],
        "description": "Требование степени образования",
        "fix": "Явно: 'Master of Laws (LL.M.), Universität Kiev, 2015'",
        "ats_format": "Полное название степени + университет + год"
    },
    "location": {
        "triggers": ["vor ort", "onsite", "präsenz", "standort", "münchen", "berlin",
                     "hamburg", "frankfurt", "relocation"],
        "description": "Требование локации",
        "fix": "Явно: 'Wohnhaft in Berlin' или 'Umzug möglich'",
        "ats_format": "Wohnort: [город]"
    },
    "experience_years": {
        "triggers": ["jahre erfahrung", "years of experience", "berufserfahrung",
                     "mindestens", "min.", "at least"],
        "description": "Минимальный опыт работы",
        "fix": "Явно в summary: 'X Jahre Berufserfahrung in...'",
        "ats_format": "[N] Jahre Berufserfahrung"
    }
}


def check_ats_filters(job_requirements: str, job_title: str, company_name: str) -> list:
    text = (job_requirements + " " + job_title + " " + company_name).lower()
    triggered = []
    for filter_id, filter_data in ATS_CRITICAL_FILTERS.items():
        for trigger in filter_data["triggers"]:
            if trigger in text:
                triggered.append({
                    "id": filter_id,
                    "description": filter_data["description"],
                    "fix": filter_data["fix"],
                    "ats_format": filter_data["ats_format"]
                })
                break
    return triggered


# groq_ask_async и clean_json теперь импортируются из modules.llm_client

LANG_DISPLAY_NAMES = {
    "DE": "Deutsch", "EN": "Englisch", "RU": "Russisch", "UK": "Ukrainisch",
    "FR": "Französisch", "ES": "Spanisch", "IT": "Italienisch", "PL": "Polnisch",
    "AR": "Arabisch", "PS": "Paschtu"
}


def _build_language_section(languages: list) -> dict:
    """Строит language_section СТРОГО из profile['languages'], без участия LLM.
    Исключает любые выдумки/конвертацию уровня (например Grundkenntnisse -> A1, fließend -> C2)."""
    german, english, other = "", "", []
    for entry in languages or []:
        code = (entry.get("lang") or "").upper()
        level = (entry.get("level") or "").strip()
        if not level:
            continue
        name = LANG_DISPLAY_NAMES.get(code, code.title() if code else "Sprache")
        line = f"{name}: {level}"
        if code == "DE":
            german = line
        elif code == "EN":
            english = line
        else:
            other.append(line)
    return {"german": german, "english": english, "other": other}


async def adapt_cv(
    profile: dict,
    company: dict,
    job: dict = None,
    lang: str = "ru"
) -> dict:
    lang_name = LANG_NAMES.get(lang, "русском языке")

    company_name = company.get("name", "")
    company_address = company.get("address", "")
    company_website = company.get("website", "")

    job_title = job.get("title", "") if job else ""
    job_requirements = job.get("requirements", "") if job else ""
    job_match_reason = job.get("match_reason", "") if job else ""

    triggered_filters = check_ats_filters(job_requirements, job_title, company_name)

    filters_context = ""
    if triggered_filters:
        filters_context = "\n⚠️ КРИТИЧЕСКИЕ ATS-ФИЛЬТРЫ — ЗАКРЫТЬ ВСЕ ОБЯЗАТЕЛЬНО:\nРеальный пример: BRYTER отклонил кандидата автоматически из-за уровня языка.\nHR не читал резюме — ATS отсеял раньше.\n\n"
        for f in triggered_filters:
            filters_context += f"🔴 {f['description']}\n"
            filters_context += f"   Как закрыть: {f['fix']}\n"
            filters_context += f"   Формат для ATS: {f['ats_format']}\n\n"

    job_context = ""
    if job_title:
        job_context = f"\nКОНКРЕТНАЯ ВАКАНСИЯ:\n- Должность: {job_title}\n- Требования: {job_requirements}\n- Почему подходит: {job_match_reason}\n\nАдаптируй CV ТОЧНО под эту вакансию.\n"
    else:
        job_context = f"\nКонкретная вакансия не найдена. Адаптируй CV под профиль компании {company_name}.\n"

    prompt = f"""Ты — эксперт по ATS-оптимизации резюме для немецкого рынка труда.

РЕАЛЬНЫЙ ПРИМЕР ПРОВАЛА:
Кандидат получил автоотказ от BRYTER:
"your current proficiency in one or more of our required languages doesn't yet meet the level"
HR не читал резюме — ATS отклонил автоматически потому что уровень языка не был в нужном формате.
Твоя задача — не допустить такого.

{filters_context}

ПРАВИЛА:
1. Закрой ВСЕ критические фильтры явно и в правильном формате
2. Уровни языков — ТОЛЬКО из profile["languages"], дословно как там указано (например A2, B1, Grundkenntnisse, fließend, Muttersprache). НИКОГДА не завышай и не изобретай уровень, даже если вакансия требует выше. Если реальный уровень ниже требуемого — честно отметь это в adaptation_notes, а не скрывай подменой цифры.
3. Опыт явно цифрами: "5 Jahre Berufserfahrung in..."
4. Образование полностью: название + университет + год
5. Локация явно: город проживания
6. Точные ключевые слова из требований (не синонимы)
7. НИКОГДА не изобретай факты о кандидате (уровень языков, стаж, образование, разрешение на работу, сертификаты) — используй ТОЛЬКО то, что явно есть в ПРОФИЛЬ КАНДИДАТА ниже. Отсутствующий факт — это не пробел, который нужно заполнить выдумкой, а данность, с которой нужно работать честно.

ПРОФИЛЬ КАНДИДАТА:
{json.dumps(profile, ensure_ascii=False, indent=2)}

КОМПАНИЯ: {company_name} | {company_address} | {company_website}

{job_context}

Верни JSON без markdown:
{{
  "company_name": "{company_name}",
  "job_title_target": "целевая должность на немецком",
  "professional_summary_de": "Резюме 3-4 предложения НА НЕМЕЦКОМ — явно: опыт N лет, уровни языков, локация. Тип опыта (управленческий/юридический/технический и т.д.) характеризуй ТОЛЬКО на основе profile['work_history']: если роли смешанные — укажи честно обе части (например 'N лет юридического опыта, из них M лет на руководящих позициях'), не обобщай одним ярлыком весь стаж",
  "professional_summary_candidate_lang": "То же на {lang_name}",
  "language_section": {{
    "german": "Deutsch: [уровень] ([пояснение])",
    "english": "Englisch: [уровень] ([пояснение])",
    "other": ["Ukrainisch: Muttersprache"]
  }},
  "personal_data_de": {{
    "location": "Stadt, Deutschland",
    "work_permit": "EU-Bürger / Niederlassungserlaubnis / etc",
    "availability": "sofort verfügbar / ab [дата]"
  }},
  "key_skills_adapted": ["навык 1", "навык 2", "навык 3", "навык 4", "навык 5"],
  "experience_highlights": [
    {{
      "role": "должность",
      "company": "компания",
      "duration": "период",
      "achievements_de": ["достижение с цифрами на немецком"]
    }}
  ],
  "ats_keywords": ["keyword1", "keyword2", "keyword3"],
  "ats_filters_closed": ["закрытый фильтр 1 — как закрыт", "фильтр 2"],
  "cover_letter_angle": "Главный аргумент почему этот кандидат подходит этой компании",
  "adaptation_notes": "Что изменено и почему — для кандидата на {lang_name}"
}}"""

    try:
        result = await groq_ask_async(prompt)
        result = clean_json(result)
        adapted = json.loads(result, strict=False)
        adapted["language_section"] = _build_language_section(profile.get("languages", []))

        adapted["company"] = company
        adapted["job"] = job
        adapted["triggered_ats_filters"] = triggered_filters
        adapted["original_profile"] = {
            "name": profile.get("name", ""),
            "location": profile.get("location", ""),
            "languages": profile.get("languages", []),
            "experience_years": profile.get("experience_years", 0),
            "work_history": profile.get("work_history", []),
        }
        return adapted

    except Exception as e:
        logging.error(f"CV Adapter error: {e}", exc_info=True)
        return {
            "company_name": company_name,
            "job_title_target": job_title or (profile.get("cross_domain_opportunities") or [""])[0],
            "professional_summary_de": "",
            "professional_summary_candidate_lang": "",
            "language_section": _build_language_section(profile.get("languages", [])),
            "personal_data_de": {},
            "key_skills_adapted": profile.get("skills", [])[:8],
            "experience_highlights": [],
            "ats_keywords": profile.get("ats_keywords", []),
            "ats_filters_closed": [],
            "cover_letter_angle": "",
            "adaptation_notes": "Адаптация не удалась",
            "triggered_ats_filters": triggered_filters,
            "company": company,
            "job": job,
            "original_profile": {
                "name": profile.get("name", ""),
                "location": profile.get("location", ""),
                "languages": profile.get("languages", []),
                "experience_years": profile.get("experience_years", 0),
                "work_history": profile.get("work_history", []),
            }
        }


async def adapt_cv_for_companies(profile: dict, companies: list, lang: str = "ru") -> list:
    semaphore = asyncio.Semaphore(3)

    async def adapt_one(company: dict) -> dict:
        async with semaphore:
            jobs = company.get("jobs", [])
            best_job = max(jobs, key=lambda j: j.get("match_score", 0)) if jobs else None
            return await adapt_cv(profile, company, best_job, lang)

    results = await asyncio.gather(*[adapt_one(c) for c in companies], return_exceptions=True)
    return [item for item in results if isinstance(item, dict)]


def format_adaptation_message(adapted: dict, lang: str = "ru") -> str:
    company_name = adapted.get("company_name", "")
    job_title = adapted.get("job_title_target", "")
    summary = adapted.get("professional_summary_candidate_lang", "")
    skills = adapted.get("key_skills_adapted", [])
    ats_keywords = adapted.get("ats_keywords", [])
    ats_filters_closed = adapted.get("ats_filters_closed", [])
    triggered = adapted.get("triggered_ats_filters", [])
    angle = adapted.get("cover_letter_angle", "")
    notes = adapted.get("adaptation_notes", "")
    lang_section = adapted.get("language_section", {})

    msg = f"📄 **Резюме адаптировано под: {company_name}**\n"
    if job_title:
        msg += f"🎯 Целевая должность: **{job_title}**\n\n"

    if summary:
        msg += f"📋 **Профессиональное резюме:**\n{summary}\n\n"

    if lang_section:
        msg += "🗣️ **Языки (для ATS):**\n"
        if lang_section.get("german"):
            msg += f"  • {lang_section['german']}\n"
        if lang_section.get("english"):
            msg += f"  • {lang_section['english']}\n"
        for other in lang_section.get("other", []):
            msg += f"  • {other}\n"
        msg += "\n"

    if triggered:
        msg += f"🛡️ **Закрытые ATS-фильтры ({len(ats_filters_closed)}/{len(triggered)}):**\n"
        for f in ats_filters_closed:
            msg += f"  ✅ {f}\n"
        msg += "\n"

    if skills:
        msg += "🛠️ **Ключевые навыки:**\n"
        for s in skills[:6]:
            msg += f"  • {s}\n"
        msg += "\n"

    if ats_keywords:
        msg += f"🔑 **ATS ключевые слова:** {', '.join(ats_keywords[:8])}\n\n"

    if angle:
        msg += f"💡 **Главный аргумент:**\n{angle}\n\n"

    if notes:
        msg += f"ℹ️ **Что изменено:** {notes}\n"

    return msg