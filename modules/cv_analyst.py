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
# БАЗА ЗНАНИЙ: БАРЬЕРЫ И WORKAROUNDS ДЛЯ КРИТИЧЕСКОГО АНАЛИЗА
# ============================================================
# Расширенная база — критический агент знает больше чем парсер
BARRIER_KNOWLEDGE = {
    "юрист": {
        "hard_barriers": [
            "Staatsexamen обязателен для адвокатской практики — невозможно обойти без 2-3 лет учёбы",
            "Нотариусом в Германии может быть только гражданин ЕС со Staatsexamen",
            "Staatsanwalt (прокурор) и Richter (судья) — только для граждан Германии",
        ],
        "soft_barriers": [
            "Незнание немецкого права снижает ценность в локальных фирмах",
            "Немецкие работодатели часто не понимают ценность иностранного юридического образования",
        ],
        "high_value_paths": [
            {
                "role": "Compliance Officer / Manager",
                "why": "Иностранное правовое мышление + понимание международных норм = преимущество",
                "demand": "высокий",
                "german_needed": "B2",
                "companies": ["банки", "страховые", "фармацевтические компании", "tech компании"]
            },
            {
                "role": "Legal Counsel (международное право)",
                "why": "Крупные немецкие компании с иностранными операциями ценят знание права СНГ/MENA",
                "demand": "средний",
                "german_needed": "B1-B2",
                "companies": ["DAX компании", "международные юрфирмы", "консалтинг"]
            },
            {
                "role": "Data Privacy Officer / GDPR Specialist",
                "why": "GDPR требует юридического мышления, не требует немецкого Staatsexamen",
                "demand": "очень высокий",
                "german_needed": "B2",
                "companies": ["все компании с EU данными", "tech стартапы", "e-commerce"]
            },
            {
                "role": "LegalTech Product Manager / Consultant",
                "why": "Автоматизация юридических процессов — растущий рынок, нужен юрист + tech понимание",
                "demand": "высокий",
                "german_needed": "B1",
                "companies": ["LegalTech стартапы", "юрфирмы с цифровизацией", "консалтинг"]
            },
            {
                "role": "Contract Manager",
                "why": "Управление договорами не требует лицензии, нужен только юридический опыт",
                "demand": "высокий",
                "german_needed": "B2",
                "companies": ["производственные", "логистика", "строительство", "IT"]
            },
        ]
    },
    "врач": {
        "hard_barriers": [
            "Approbation обязательна для самостоятельной врачебной практики",
            "Процесс апробации: 6 месяцев — 2 года в зависимости от земли и диплома",
            "Обязательный немецкий C1 (Fachsprachprüfung — медицинский язык)",
        ],
        "soft_barriers": [
            "Немецкие пациенты ожидают коммуникации на немецком языке",
            "Разные медицинские протоколы и стандарты",
        ],
        "high_value_paths": [
            {
                "role": "Medical Science Liaison (MSL)",
                "why": "Фармкомпании ищут врачей как мост между наукой и коммерцией",
                "demand": "высокий",
                "german_needed": "B2",
                "companies": ["Bayer", "Roche", "Pfizer", "Novartis", "Boehringer"]
            },
            {
                "role": "Clinical Research Associate (CRA)",
                "why": "Клинические исследования требуют медицинского образования, не Approbation",
                "demand": "очень высокий",
                "german_needed": "B1",
                "companies": ["CRO компании", "фармацевтические", "медицинские институты"]
            },
            {
                "role": "Health IT / Digital Health Consultant",
                "why": "Цифровизация медицины требует специалистов, которые понимают и медицину и IT",
                "demand": "очень высокий",
                "german_needed": "B1",
                "companies": ["Siemens Healthineers", "Philips", "MedTech стартапы", "больничные сети"]
            },
            {
                "role": "Berufserlaubnis (временная практика)",
                "why": "Можно работать врачом-ассистентом пока идёт апробация — быстрый старт",
                "demand": "высокий",
                "german_needed": "B2",
                "companies": ["государственные больницы", "частные клиники"]
            },
        ]
    },
    "учитель": {
        "hard_barriers": [
            "Verbeamtung (госслужба) недоступна без гражданства ЕС",
            "Каждая земля признаёт квалификацию отдельно — нет единого стандарта",
        ],
        "soft_barriers": [
            "Немецкая педагогическая система существенно отличается от восточноевропейской",
        ],
        "high_value_paths": [
            {
                "role": "Sprachlehrer (русский/арабский/украинский)",
                "why": "Носители языка востребованы в VHS, языковых школах и онлайн",
                "demand": "высокий",
                "german_needed": "B1",
                "companies": ["Volkshochschule", "Berlitz", "частные языковые школы"]
            },
            {
                "role": "Corporate Trainer / L&D Specialist",
                "why": "Педагогические компетенции применимы в корпоративном обучении без лицензий",
                "demand": "высокий",
                "german_needed": "B2",
                "companies": ["крупные корпорации", "консалтинговые фирмы", "HR агентства"]
            },
            {
                "role": "Internationale Schule",
                "why": "Международные школы признают иностранные квалификации напрямую",
                "demand": "средний",
                "german_needed": "A2-B1",
                "companies": ["Internationale Schulen", "европейские школы", "американские школы"]
            },
        ]
    },
    "инженер": {
        "hard_barriers": [],
        "soft_barriers": [
            "Для проектировщиков в строительстве может потребоваться Ingenieurkammer",
        ],
        "high_value_paths": [
            {
                "role": "Software/Automation Engineer",
                "why": "Инженерный диплом + программирование = прямой путь без барьеров",
                "demand": "очень высокий",
                "german_needed": "A2-B1",
                "companies": ["Siemens", "Bosch", "BMW", "SAP", "любые tech компании"]
            },
        ]
    },
    "бухгалтер": {
        "hard_barriers": [
            "Steuerberater требует немецкого государственного экзамена",
        ],
        "soft_barriers": [
            "Немецкое налоговое право (HGB, DATEV) существенно отличается от других систем",
        ],
        "high_value_paths": [
            {
                "role": "Controller / Financial Analyst",
                "why": "Контроллинг не требует лицензии, высоко ценится в немецких компаниях",
                "demand": "высокий",
                "german_needed": "B2",
                "companies": ["производственные", "торговые", "все средние и крупные компании"]
            },
            {
                "role": "SAP FI/CO Consultant",
                "why": "SAP знание + бухгалтерский опыт = очень востребованная комбинация",
                "demand": "очень высокий",
                "german_needed": "B1",
                "companies": ["SAP partners", "крупные корпорации", "консалтинг"]
            },
        ]
    },
}

# ============================================================
# ПАТТЕРНЫ УСИЛЕНИЯ ПРОФИЛЯ
# ============================================================
POWER_COMBINATIONS = [
    # Юридические
    {"tags": ["legal", "gdpr", "privacy"], "boost": "GDPR/Data Privacy Expert — дефицитная специальность"},
    {"tags": ["legal", "fintech"], "boost": "RegTech Specialist — финансовая регуляторика"},
    {"tags": ["legal", "healthcare"], "boost": "Healthcare Compliance — медицинские регуляции"},
    # Технические
    {"tags": ["python", "data"], "boost": "Data Engineer/Scientist — одна из самых востребованных ролей"},
    {"tags": ["python", "automation"], "boost": "Process Automation Specialist — RPA и автоматизация бизнес-процессов"},
    {"tags": ["cloud", "devops"], "boost": "Cloud/DevOps Engineer — критический дефицит специалистов"},
    # Языковые
    {"tags": ["arabic", "german"], "boost": "MENA-DACH Bridge — ценный посредник для ближневосточного бизнеса"},
    {"tags": ["russian", "german"], "boost": "CIS-DACH Specialist — востребован в компаниях с СНГ операциями"},
    {"tags": ["ukrainian", "german"], "boost": "UA-DE Integration Specialist — актуально в текущем контексте"},
    # Межотраслевые
    {"tags": ["medical", "management"], "boost": "Healthcare Management — управление медицинскими организациями"},
    {"tags": ["teaching", "corporate"], "boost": "Learning & Development (L&D) Manager"},
    {"tags": ["engineering", "sales"], "boost": "Technical Sales / Pre-Sales Engineer — высокая зарплата"},
    {"tags": ["finance", "risk"], "boost": "Risk Manager — банки и страховые компании"},
]


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


def detect_power_combinations(profile: dict, qa_answers: str) -> list:
    """Ищет усиливающие комбинации в профиле и ответах кандидата."""
    combined = (
        json.dumps(profile, ensure_ascii=False) + " " + qa_answers
    ).lower()

    found = []
    for combo in POWER_COMBINATIONS:
        if all(tag in combined for tag in combo["tags"]):
            found.append(combo["boost"])
    return found


# ============================================================
# КРИТИЧЕСКИЙ АНАЛИЗ ПРОФИЛЯ
# ============================================================
async def analyze_profile(
    profile: dict,
    qa_pairs: list,
    lang: str = "ru"
) -> dict:
    """
    Критический агент — глубокая переоценка профиля после диалога.

    Отличие от cv_parser:
    - cv_parser извлекает и структурирует данные
    - cv_analyst ПЕРЕОСМЫСЛИВАЕТ: находит скрытые пути, оценивает реальные шансы,
      даёт честную оценку барьеров и конкретные следующие шаги

    Args:
        profile: профиль из cv_parser
        qa_pairs: список {"question": "...", "answer": "..."} из диалога
        lang: язык кандидата

    Returns:
        Усиленный профиль с полем "analyst_report"
    """
    lang_name = LANG_NAMES.get(lang, "русском языке")

    # Формируем контекст диалога
    qa_text = "\n".join([
        f"Вопрос: {pair.get('question', '')}\nОтвет: {pair.get('answer', '')}"
        for pair in qa_pairs
    ])
    qa_answers_raw = " ".join([pair.get('answer', '') for pair in qa_pairs])

    # Собираем барьерный контекст из базы знаний
    detected_professions = profile.get("detected_professions", [])
    barrier_context = ""
    high_value_paths_context = ""

    for prof in detected_professions:
        if prof in BARRIER_KNOWLEDGE:
            kb = BARRIER_KNOWLEDGE[prof]
            if kb.get("hard_barriers"):
                barrier_context += f"\nЖЁСТКИЕ БАРЬЕРЫ ({prof}):\n"
                barrier_context += "\n".join(f"- {b}" for b in kb["hard_barriers"])
            if kb.get("soft_barriers"):
                barrier_context += f"\nМЯГКИЕ БАРЬЕРЫ ({prof}):\n"
                barrier_context += "\n".join(f"- {b}" for b in kb["soft_barriers"])
            if kb.get("high_value_paths"):
                high_value_paths_context += f"\nВЫСОКОЦЕННЫЕ ПУТИ ДЛЯ {prof.upper()}:\n"
                for path in kb["high_value_paths"]:
                    high_value_paths_context += (
                        f"- {path['role']}: {path['why']} "
                        f"(спрос: {path['demand']}, немецкий: {path['german_needed']})\n"
                    )

    # Ищем усиливающие комбинации
    power_combos = detect_power_combinations(profile, qa_answers_raw)
    power_context = ""
    if power_combos:
        power_context = "\nОБНАРУЖЕНЫ УСИЛИВАЮЩИЕ КОМБИНАЦИИ:\n"
        power_context += "\n".join(f"⚡ {c}" for c in power_combos)

    prompt = f"""Ты — старший карьерный консультант и критический аналитик рынка труда DACH.
Твоя работа — честно и глубоко оценить реальные шансы кандидата и найти ЛУЧШИЙ путь.

ЯЗЫК ОТВЕТА: Все поля JSON — ИСКЛЮЧИТЕЛЬНО на {lang_name}.
Исключение: search_queries — только на немецком.

═══════════════════════════════════════
ИСХОДНЫЙ ПРОФИЛЬ КАНДИДАТА:
{json.dumps(profile, ensure_ascii=False, indent=2)}

═══════════════════════════════════════
ДИАЛОГ С КАНДИДАТОМ (новая информация):
{qa_text}

═══════════════════════════════════════
КОНТЕКСТ ИЗ БАЗЫ ЗНАНИЙ:
{barrier_context}
{high_value_paths_context}
{power_context}

═══════════════════════════════════════
ТВОИ ЗАДАЧИ:

1. КРИТИЧЕСКАЯ ПЕРЕОЦЕНКА
   Что изменилось после диалога? Какие новые факты открылись?
   Был ли первичный анализ точным или упустил что-то важное?

2. РЕАЛЬНАЯ ОЦЕНКА ШАНСОВ
   По каждому пути — честно: HIGH / MEDIUM / LOW + почему.
   Не обнадёживай зря, но и не занижай реальные возможности.

3. СТРАТЕГИЯ ОБХОДА БАРЬЕРОВ
   Для каждого жёсткого барьера — конкретный план обхода.
   Не "рассмотрите переквалификацию" — а "вот конкретно что делать за 3 месяца".

4. ПЕРЕОСМЫСЛЕНИЕ ПРОФИЛЯ
   Как позиционировать кандидата так, чтобы его уникальный бэкграунд
   стал ПРЕИМУЩЕСТВОМ, а не недостатком?

5. КОНКРЕТНЫЕ СЛЕДУЮЩИЕ ШАГИ
   3-5 действий которые кандидат должен сделать на этой неделе.

6. ОБНОВЛЁННЫЕ ПОИСКОВЫЕ ЗАПРОСЫ
   Уточни search_queries с учётом новой информации из диалога.

Отвечай СТРОГО в JSON без markdown:
{{
  "name": "имя из профиля",
  "location": "локация",
  "experience_years": 0,
  "primary_domain": "обновлённая сфера",
  "skills": ["навык 1", "навык 2"],
  "languages": [{{"lang": "DE", "level": "B2"}}],
  "hidden_competencies": ["компетенция 1", "компетенция 2"],
  "cross_domain_opportunities": ["роль 1", "роль 2"],
  "target_companies_dach": ["тип компании 1", "тип компании 2"],
  "search_queries": ["немецкий запрос 1", "немецкий запрос 2", "немецкий запрос 3"],
  "barriers": ["барьер 1", "барьер 2"],
  "workarounds": ["обходной путь 1", "обходной путь 2"],
  "analyst_report": {{
    "critical_insights": [
      "ключевое открытие 1 после анализа диалога",
      "ключевое открытие 2"
    ],
    "chances_assessment": [
      {{"path": "название пути", "level": "HIGH/MEDIUM/LOW", "reason": "почему"}},
      {{"path": "название пути", "level": "HIGH/MEDIUM/LOW", "reason": "почему"}}
    ],
    "repositioning_strategy": "как именно позиционировать кандидата — 2-3 предложения",
    "barrier_bypass_plan": [
      {{"barrier": "название барьера", "plan": "конкретный план обхода за 3-6 месяцев"}}
    ],
    "next_steps": [
      "конкретное действие 1 — сделать на этой неделе",
      "конкретное действие 2",
      "конкретное действие 3"
    ],
    "power_combinations": {power_combos if power_combos else []}
  }}
}}"""

    try:
        result = await groq_ask_async(prompt)
        result = clean_json(result)
        enriched = json.loads(result)

        # Сохраняем метаданные из оригинала
        enriched["detected_professions"] = profile.get("detected_professions", [])
        enriched["has_barriers"] = bool(enriched.get("barriers"))
        enriched["hidden_patterns"] = profile.get("hidden_patterns", [])

        # Добавляем power_combinations если LLM их потеряла
        if power_combos and not enriched.get("analyst_report", {}).get("power_combinations"):
            enriched.setdefault("analyst_report", {})["power_combinations"] = power_combos

        return enriched

    except Exception as e:
        logging.error(f"CV Analyst error: {e}")
        # Возвращаем оригинальный профиль с пометкой об ошибке
        profile["analyst_report"] = {
            "critical_insights": ["Анализ не удался — используется исходный профиль"],
            "chances_assessment": [],
            "repositioning_strategy": "",
            "barrier_bypass_plan": [],
            "next_steps": [],
            "power_combinations": power_combos
        }
        return profile


# ============================================================
# ФОРМАТИРОВАНИЕ ОТЧЁТА АНАЛИТИКА ДЛЯ ЧАТА
# ============================================================
def format_analyst_report(profile: dict, lang: str = "ru") -> str:
    """Форматирует отчёт критического агента для показа кандидату."""

    report = profile.get("analyst_report", {})
    if not report:
        return ""

    msg = "🔬 **Углублённый анализ вашего профиля**\n\n"

    # Ключевые открытия
    insights = report.get("critical_insights", [])
    if insights:
        msg += "💡 **Ключевые выводы:**\n"
        for insight in insights:
            msg += f"  • {insight}\n"
        msg += "\n"

    # Стратегия позиционирования
    strategy = report.get("repositioning_strategy", "")
    if strategy:
        msg += f"🎯 **Стратегия позиционирования:**\n{strategy}\n\n"

    # Оценка шансов
    chances = report.get("chances_assessment", [])
    if chances:
        msg += "📊 **Оценка шансов по направлениям:**\n"
        icons = {"HIGH": "🟢", "MEDIUM": "🟡", "LOW": "🔴"}
        for item in chances:
            icon = icons.get(item.get("level", ""), "⚪")
            msg += f"  {icon} **{item.get('path', '')}** — {item.get('reason', '')}\n"
        msg += "\n"

    # Power combinations
    power = report.get("power_combinations", [])
    if power:
        msg += "⚡ **Уникальные комбинации навыков:**\n"
        for p in power:
            msg += f"  • {p}\n"
        msg += "\n"

    # План обхода барьеров
    bypass = report.get("barrier_bypass_plan", [])
    if bypass:
        msg += "🔓 **План обхода барьеров:**\n"
        for item in bypass:
            msg += f"  ⚠️ **{item.get('barrier', '')}**\n"
            msg += f"     → {item.get('plan', '')}\n"
        msg += "\n"

    # Следующие шаги
    steps = report.get("next_steps", [])
    if steps:
        msg += "✅ **Следующие шаги (эта неделя):**\n"
        for i, step in enumerate(steps, 1):
            msg += f"  {i}. {step}\n"
        msg += "\n"

    return msg