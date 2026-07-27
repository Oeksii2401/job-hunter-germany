import os
import json
import re
from groq import Groq

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# ============================================================
# БАЗА БАРЬЕРОВ ПО ПРОФЕССИЯМ В ГЕРМАНИИ
# ============================================================
PROFESSION_BARRIERS = {
    "юрист": {
        "keywords": ["юрист", "lawyer", "rechtsanwalt", "attorney", "правовед", "legal", "право", "jura", "jurist"],
        "barriers": [
            "Для практики адвокатом в Германии требуется немецкий Staatsexamen (две государственные экзаменации)",
            "Иностранный диплом юриста НЕ признаётся автоматически для адвокатской деятельности",
            "Процедура признания через Rechtsanwaltskammer занимает 6-18 месяцев и часто требует дополнительных экзаменов",
        ],
        "workarounds": [
            "Compliance Manager / Compliance Officer — не требует немецкого Staatsexamen, иностранный опыт ценится",
            "Legal Counsel в международных компаниях — работа по корпоративному праву страны происхождения",
            "LegalTech специалист — если есть технический бэкграунд (особенно Python, AI, автоматизация)",
            "Paralegal / Legal Assistant — поддержка немецких юристов, путь к погружению в систему",
            "Contract Manager — управление договорами, не требует адвокатской лицензии",
            "Юридический консультант для иностранных компаний в Германии (специалист по праву своей страны)",
            "Академическая карьера / исследования в немецком университете",
        ],
        "reframe": "Иностранный юрист в Германии — это прежде всего эксперт по международному праву и комплаенсу, а не адвокат местной практики."
    },
    "врач": {
        "keywords": ["врач", "doctor", "arzt", "медик", "physician", "surgeon", "хирург", "терапевт", "педиатр", "medicina", "медицина"],
        "barriers": [
            "Для работы врачом требуется Approbation (государственное признание диплома)",
            "Процедура апробации: перевод диплома → Landesprüfungsamt → анализ программы обучения → возможный Kenntnisprüfung (экзамен на знания)",
            "Обязательный уровень немецкого: минимум C1 (для психотерапевтов — C2)",
            "Срок процедуры: от 6 месяцев до 2 лет в зависимости от земли",
        ],
        "workarounds": [
            "Berufserlaubnis — временное разрешение на работу ассистентом врача, пока идёт апробация",
            "Forschung (исследования) — работа в медицинских НИИ не требует Approbation",
            "Pharmaunternehmen — медицинский советник / Medical Science Liaison",
            "Medizinische Informatik — если есть IT-навыки, сочетание медицины и технологий очень востребовано",
            "Krankenhaus-Management — административные роли в больницах",
        ],
        "reframe": "Врач без апробации — потенциальный медицинский советник, исследователь или MedTech специалист."
    },
    "учитель": {
        "keywords": ["учитель", "teacher", "lehrer", "педагог", "преподаватель", "educator", "schullehrer"],
        "barriers": [
            "Признание учительской квалификации — компетенция каждой федеральной земли отдельно",
            "Немецкая система имеет специфическую структуру (Gymnasium, Realschule, Hauptschule) без аналогов",
            "Госслужба (Beamter) требует немецкого гражданства или ВНЖ + возрастные ограничения",
        ],
        "workarounds": [
            "Internationale Schulen (международные школы) — признают иностранную квалификацию",
            "Privatschulen — частные школы имеют больше гибкости в найме",
            "Volkshochschule (VHS) — курсы для взрослых, почти без ограничений по квалификации",
            "Sprachlehrer — преподавание родного языка (особенно востребованы русский, арабский, китайский)",
            "Unternehmensberatung (корпоративное обучение) — тренинги в компаниях",
            "Online-Lehrer — дистанционное преподавание без немецкой лицензии",
        ],
        "reframe": "Педагог из другой страны — идеальный учитель иностранных языков и корпоративных тренингов."
    },
    "архитектор": {
        "keywords": ["архитектор", "architect", "architekt", "проектировщик", "градостроитель"],
        "barriers": [
            "Для использования титула 'Architekt' требуется регистрация в Architektenkammer (земельная палата архитекторов)",
            "Иностранный диплом признаётся через процедуру Berufsanerkennung",
        ],
        "workarounds": [
            "Работа как дизайнер/проектировщик без официального титула 'Architekt'",
            "BIM-специалист — Building Information Modeling, очень востребован",
            "Technischer Zeichner / CAD-Spezialist",
            "Innenarchitektur — отдельная специальность с чуть проще признанием",
        ],
        "reframe": "Архитектор без немецкой лицензии — эксперт BIM и международного проектирования."
    },
    "инженер": {
        "keywords": ["инженер", "engineer", "ingenieur", "механик", "электрик", "конструктор"],
        "barriers": [
            "Инженерный диплом в целом хорошо признаётся, но для некоторых специальностей (строительство, энергетика) может требоваться Kammermitgliedschaft",
        ],
        "workarounds": [
            "Большинство технических инженерных должностей доступны напрямую",
            "Ingenieurkammer — при необходимости процедура признания относительно быстрая",
        ],
        "reframe": "Инженерная квалификация — одна из лучших для трудоустройства в Германии."
    },
    "бухгалтер": {
        "keywords": ["бухгалтер", "accountant", "buchhalter", "финансист", "аудитор", "steuerberater", "налоговый"],
        "barriers": [
            "Steuerberater (налоговый консультант) требует сдачи немецкого государственного экзамена",
            "Wirtschaftsprüfer (аудитор) — аналогично, требует немецкой лицензии",
        ],
        "workarounds": [
            "Buchhalter / Finanzbuchhalter — без лицензии, только опыт",
            "Controlling (контроллинг) — часто открыт для иностранных специалистов",
            "SAP-специалист — если есть знание SAP, очень востребован",
            "Finanzanalyst в международных компаниях",
        ],
        "reframe": "Бухгалтер без немецкой лицензии — отличный кандидат в контроллинг и финансовый анализ."
    },
    "психолог": {
        "keywords": ["психолог", "psychologist", "psychologe", "психотерапевт", "therapist"],
        "barriers": [
            "Психотерапевт (Psychotherapeut) — строго лицензируемая профессия, требует немецкого признания",
            "Требование немецкого C2 для психотерапевтической практики",
        ],
        "workarounds": [
            "Psychologischer Berater (консультант) — без лицензии терапевта",
            "HR / Personalentwicklung — применение психологических знаний в бизнесе",
            "Coaching — без государственной лицензии",
            "UX Research — психология пользовательского опыта",
            "Forschung в университетах и институтах",
        ],
        "reframe": "Психолог без немецкой лицензии — ценный HR-эксперт, коуч и UX-исследователь."
    }
}

# ============================================================
# ОПРЕДЕЛЕНИЕ ПРОФЕССИИ ИЗ ПРОФИЛЯ
# ============================================================
def detect_profession(cv_text: str) -> list:
    """Определяет профессию кандидата по ключевым словам."""
    cv_lower = cv_text.lower()
    detected = []
    for profession, data in PROFESSION_BARRIERS.items():
        for keyword in data["keywords"]:
            if keyword in cv_lower:
                detected.append(profession)
                break
    return detected


# ============================================================
# ПОИСК СКРЫТЫХ ПАТТЕРНОВ
# ============================================================
HIDDEN_PATTERNS = [
    {
        "skills": ["юрист", "python"],
        "label": "LegalTech специалист",
        "description": "Редкая комбинация: юридические знания + программирование = LegalTech разработчик или консультант по автоматизации юридических процессов"
    },
    {
        "skills": ["юрист", "ai"],
        "label": "AI Legal Consultant",
        "description": "Юридическая экспертиза + понимание AI = специалист по регуляторике AI (EU AI Act, GDPR compliance)"
    },
    {
        "skills": ["юрист", "compliance"],
        "label": "Compliance Expert",
        "description": "Юридическое образование + compliance опыт = готовый Compliance Manager без немецкой лицензии"
    },
    {
        "skills": ["врач", "python"],
        "label": "Medical Data Scientist",
        "description": "Медицинское образование + программирование = медицинский дата-сайентист или MedTech специалист"
    },
    {
        "skills": ["врач", "it"],
        "label": "Health IT Specialist",
        "description": "Медицина + IT = цифровизация здравоохранения, telehealth, медицинские информационные системы"
    },
    {
        "skills": ["финансы", "python"],
        "label": "FinTech Developer",
        "description": "Финансовая экспертиза + программирование = FinTech специалист"
    },
    {
        "skills": ["учитель", "онлайн"],
        "label": "E-Learning Specialist",
        "description": "Педагогика + онлайн-опыт = разработчик e-learning контента и учебных программ"
    },
    {
        "skills": ["менеджер", "русский"],
        "label": "DACH-CIS Bridge Manager",
        "description": "Управленческий опыт + русскоязычный бэкграунд = ценный посредник для немецко-российских/СНГ бизнес-отношений"
    },
    {
        "skills": ["инженер", "python"],
        "label": "Industrial Automation Engineer",
        "description": "Инженерное образование + программирование = специалист по промышленной автоматизации и IoT"
    },
    {
        "skills": ["маркетинг", "ai"],
        "label": "AI Marketing Specialist",
        "description": "Маркетинговый опыт + AI-инструменты = очень востребованная роль в 2024-2025"
    },
]


def detect_hidden_patterns(cv_text: str, profile: dict) -> list:
    """Ищет неочевидные комбинации навыков."""
    cv_lower = cv_text.lower()
    profile_str = json.dumps(profile, ensure_ascii=False).lower()
    combined = cv_lower + " " + profile_str

    found_patterns = []
    for pattern in HIDDEN_PATTERNS:
        if all(skill in combined for skill in pattern["skills"]):
            found_patterns.append(pattern)
    return found_patterns


# ============================================================
# ОСНОВНОЙ ПАРСЕР CV
# ============================================================
async def parse_cv(cv_text: str, lang: str = "ru") -> dict:
    """
    Парсит CV и возвращает структурированный профиль с барьерами и workarounds.
    """

    LANG_NAMES = {
        "ru": "русском языке",
        "de": "deutscher Sprache",
        "en": "English",
        "uk": "українській мові",
        "ar": "اللغة العربية",
        "ps": "پښتو ژبه"
    }
    lang_name = LANG_NAMES.get(lang, "русском языке")

    # 1. Определяем барьеры на основе профессии
    detected_professions = detect_profession(cv_text)
    barriers_info = []
    workarounds_info = []
    reframes = []

    for prof in detected_professions:
        data = PROFESSION_BARRIERS[prof]
        barriers_info.extend(data["barriers"])
        workarounds_info.extend(data["workarounds"])
        reframes.append(data["reframe"])

    barriers_text = ""
    if barriers_info:
        barriers_text = f"""
ВАЖНО — ПРОФЕССИОНАЛЬНЫЕ БАРЬЕРЫ В ГЕРМАНИИ:
{chr(10).join(f'⚠️ {b}' for b in barriers_info)}

ОБХОДНЫЕ ПУТИ И АЛЬТЕРНАТИВЫ:
{chr(10).join(f'✅ {w}' for w in workarounds_info)}

ПЕРЕОСМЫСЛЕНИЕ ПРОФИЛЯ:
{chr(10).join(reframes)}

При анализе CV обязательно учти эти барьеры и предложи реалистичные пути трудоустройства.
"""

    prompt = f"""Ты — опытный карьерный консультант по трудоустройству в Германии (DACH регион).

Тебе нужно глубоко проанализировать CV кандидата. Не просто извлечь данные — а ПЕРЕОСМЫСЛИТЬ профиль для немецкого рынка труда.

ЯЗЫК ОТВЕТА: Все текстовые поля JSON (кроме summary_de, ats_keywords) пиши ИСКЛЮЧИТЕЛЬНО на {lang_name}.
Это критически важно — кандидат читает на этом языке.
Исключение: summary_de — на немецком, ats_keywords — на немецком/английском.

{barriers_text}

ЗАДАЧА:
1. Извлеки основные данные (имя, контакты, образование, опыт, навыки)
2. Определи РЕАЛЬНЫЕ возможности в Германии с учётом барьеров
3. Найди НЕОЧЕВИДНЫЕ комбинации навыков и опыта
4. Сформулируй сильные стороны в немецком контексте
5. Укажи конкретные должности (job titles) на немецком рынке
6. Задай 3 умных уточняющих вопроса на {lang_name}
   ЗАПРЕЩЕНО спрашивать про барьеры (Staatsexamen, признание диплома) — кандидат их и так знает
   ЗАПРЕЩЕНО спрашивать про немецкое право или немецкий язык — это очевидно из CV
   НУЖНО спрашивать про: скрытые навыки, реальные интересы, опыт который не в CV, AI/tech проекты

CV КАНДИДАТА:
{cv_text}

Отвечай ТОЛЬКО в формате JSON (без markdown, без объяснений):
{{
  "name": "Имя Фамилия",
  "email": "",
  "phone": "",
  "location": "",
  "profession_raw": "Профессия из CV",
  "profession_germany": "Реалистичная профессия/роль в Германии",
  "education": ["образование"],
  "experience_years": 0,
  "experience": [
    {{"company": "", "role": "", "duration": "", "achievements": ""}}
  ],
  "skills": ["навык1", "навык2"],
  "languages": [{{"language": "", "level": ""}}],
  "barriers": ["барьер1", "барьер2"],
  "workarounds": ["обходной путь 1", "обходной путь 2"],
  "hidden_strengths": ["сильная сторона 1"],
  "hidden_competencies": ["скрытая компетенция 1"],
  "cross_domain_opportunities": ["роль 1 в DACH", "роль 2"],
  "target_roles_de": ["должность1 на немецком", "должность2"],
  "target_industries": ["отрасль1", "отрасль2"],
  "search_queries": ["немецкий поисковый запрос 1 для Google Maps", "запрос 2", "запрос 3"],
  "ats_keywords": ["keyword1", "keyword2"],
  "summary_de": "Профессиональное резюме (2-3 предложения) на немецком языке",
  "summary_ru": "Профессиональное резюме (2-3 предложения) на {lang_name}",
  "reframe": "Как позиционировать кандидата на немецком рынке",
  "clarifying_questions": [
    "конкретный умный вопрос 1 на {lang_name} — СТРОГО на {lang_name}",
    "конкретный умный вопрос 2 на {lang_name}",
    "конкретный умный вопрос 3 на {lang_name}"
  ]
}}"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=2000,
    )

    raw = response.choices[0].message.content.strip()

    # Убираем возможные markdown-обёртки
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    raw = raw.strip()

    try:
        profile = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: базовый профиль
        profile = {
            "name": "Не определено",
            "email": "",
            "phone": "",
            "location": "",
            "profession_raw": "Не определено",
            "profession_germany": "Требует уточнения",
            "education": [],
            "experience_years": 0,
            "experience": [],
            "skills": [],
            "languages": [],
            "barriers": barriers_info,
            "workarounds": workarounds_info,
            "hidden_strengths": [],
            "target_roles_de": [],
            "target_industries": [],
            "ats_keywords": [],
            "summary_de": "",
            "summary_ru": "CV обработано, но структура ответа нарушена. Пожалуйста, проверьте данные.",
            "reframe": "",
            "clarifying_questions": []
        }

    # 2. Добавляем барьеры если LLM их не нашла
    if "barriers" not in profile or not profile["barriers"]:
        profile["barriers"] = barriers_info
    if "workarounds" not in profile or not profile["workarounds"]:
        profile["workarounds"] = workarounds_info

    # 3. Ищем скрытые паттерны
    hidden_patterns = detect_hidden_patterns(cv_text, profile)
    if hidden_patterns:
        profile["hidden_patterns"] = [
            {
                "label": p["label"],
                "description": p["description"]
            }
            for p in hidden_patterns
        ]
        # Добавляем роли из паттернов в target_roles
        for p in hidden_patterns:
            if p["label"] not in profile.get("target_roles_de", []):
                profile.setdefault("target_roles_de", []).append(p["label"])
    else:
        profile["hidden_patterns"] = []

    # 4. Метаданные
    profile["detected_professions"] = detected_professions
    profile["has_barriers"] = len(barriers_info) > 0

    return profile


# ============================================================
# ФОРМАТИРОВАНИЕ ПРОФИЛЯ ДЛЯ ОТОБРАЖЕНИЯ В ЧАТЕ
# ============================================================
def format_profile_message(profile: dict, lang: str = "ru") -> str:
    """Форматирует профиль для показа пользователю."""

    name = profile.get("name", "Кандидат")
    profession_raw = profile.get("profession_raw", "")
    profession_germany = profile.get("profession_germany", "")
    summary = profile.get("summary_ru", "")
    barriers = profile.get("barriers", [])
    workarounds = profile.get("workarounds", [])
    hidden_patterns = profile.get("hidden_patterns", [])
    target_roles = profile.get("target_roles_de", [])
    skills = profile.get("skills", [])
    languages = profile.get("languages", [])
    reframe = profile.get("reframe", "")

    msg = f"✅ **Профиль создан: {name}**\n\n"

    if summary:
        msg += f"📋 {summary}\n\n"

    if profession_raw and profession_germany and profession_raw != profession_germany:
        msg += f"🎯 **Профессия:** {profession_raw}\n"
        msg += f"🇩🇪 **На рынке Германии:** {profession_germany}\n\n"

    if reframe:
        msg += f"💡 **Стратегия позиционирования:** {reframe}\n\n"

    if barriers:
        msg += "⚠️ **Важные барьеры для трудоустройства:**\n"
        for b in barriers:
            msg += f"  • {b}\n"
        msg += "\n"

    if workarounds:
        msg += "✅ **Обходные пути и возможности:**\n"
        for w in workarounds[:5]:
            msg += f"  • {w}\n"
        msg += "\n"

    if hidden_patterns:
        msg += "🔍 **Обнаружены уникальные комбинации навыков:**\n"
        for p in hidden_patterns:
            msg += f"  🌟 **{p['label']}** — {p['description']}\n"
        msg += "\n"

    if target_roles:
        msg += f"🎯 **Целевые роли в Германии:**\n"
        for role in target_roles[:6]:
            msg += f"  • {role}\n"
        msg += "\n"

    if skills:
        top_skills = skills[:8]
        msg += f"🛠️ **Ключевые навыки:** {', '.join(top_skills)}\n"

    if languages:
        lang_list = [f"{l.get('language', '')} ({l.get('level', '')})" for l in languages]
        msg += f"🗣️ **Языки:** {', '.join(lang_list)}\n"

    return msg


# ============================================================
# ГЕНЕРАЦИЯ УТОЧНЯЮЩИХ ВОПРОСОВ
# ============================================================
async def generate_questions(profile: dict, lang: str = "ru") -> list:
    """
    Генерирует уточняющие вопросы для усиления профиля.
    Учитывает барьеры и workarounds.
    """
    LANG_NAMES = {
        "ru": "русском языке",
        "de": "deutscher Sprache",
        "en": "English",
        "uk": "українській мові",
        "ar": "اللغة العربية",
        "ps": "پښتو ژبه"
    }
    lang_name = LANG_NAMES.get(lang, "русском языке")

    barriers = profile.get("barriers", [])
    workarounds = profile.get("workarounds", [])
    hidden_patterns = profile.get("hidden_patterns", [])
    target_roles = profile.get("target_roles_de", [])

    barriers_context = ""
    if barriers:
        barriers_context = f"""
Кандидат сталкивается с профессиональными барьерами:
{chr(10).join(barriers)}

Возможные пути обхода:
{chr(10).join(workarounds[:3])}

Задавай вопросы, которые помогут определить, применим ли тот или иной workaround к данному кандидату.
"""

    patterns_context = ""
    if hidden_patterns:
        patterns_context = f"""
Обнаружены потенциальные роли: {', '.join(p['label'] for p in hidden_patterns)}
Уточни, есть ли у кандидата опыт в этих направлениях.
"""

    prompt = f"""Ты — карьерный консультант. Изучи профиль кандидата и задай 4-5 умных уточняющих вопроса.

ПРОФИЛЬ:
{json.dumps(profile, ensure_ascii=False, indent=2)}

{barriers_context}
{patterns_context}

ЦЕЛЬ ВОПРОСОВ:
1. Выявить скрытые преимущества, не отражённые в CV
2. Понять применимость обходных путей
3. Уточнить мотивацию и предпочтения
4. Найти конкурентные преимущества на немецком рынке
5. Определить готовность к переобучению или смене направления

ФОРМАТ ОТВЕТА — только JSON массив строк:
["Вопрос 1?", "Вопрос 2?", "Вопрос 3?", "Вопрос 4?", "Вопрос 5?"]

Вопросы на {lang_name} — СТРОГО на этом языке, никакого немецкого если язык не немецкий.
Вопросы должны быть конкретными, не общими ("расскажите о себе" — плохо).
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5,
        max_tokens=500,
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    raw = raw.strip()

    try:
        questions = json.loads(raw)
        if isinstance(questions, list):
            return questions[:5]
    except json.JSONDecodeError:
        pass

    # Fallback вопросы
    return [
        "Есть ли у вас опыт работы с немецкими компаниями или в немецкоязычной среде?",
        "Какой у вас текущий уровень немецкого языка?",
        "Рассматриваете ли вы переобучение или дополнительную сертификацию в Германии?",
        "Есть ли у вас опыт в сферах, не отражённых в CV (волонтёрство, проекты, фриланс)?",
        "В каком городе или регионе Германии вы ищете работу?"
    ]


# ============================================================
# ОБНОВЛЕНИЕ ПРОФИЛЯ ПОСЛЕ ДИАЛОГА
# ============================================================
async def enrich_profile(profile: dict, qa_pairs: list, lang: str = "ru") -> dict:
    """
    Обновляет и усиливает профиль после диалога с кандидатом.
    qa_pairs: список {"question": "...", "answer": "..."}
    """

    qa_text = "\n".join([
        f"Q: {pair.get('question', '')}\nA: {pair.get('answer', '')}"
        for pair in qa_pairs
    ])

    prompt = f"""Ты — опытный карьерный консультант. 
На основе исходного профиля CV и ответов кандидата на вопросы — создай УСИЛЕННЫЙ финальный профиль.

ИСХОДНЫЙ ПРОФИЛЬ:
{json.dumps(profile, ensure_ascii=False, indent=2)}

ДИАЛОГ С КАНДИДАТОМ:
{qa_text}

ЗАДАЧА:
1. Переоцени профиль с учётом новой информации
2. Найди новые возможности, которые не были видны из CV
3. Скорректируй целевые роли и стратегию
4. Усиль позиционирование для немецкого рынка
5. Обнови ATS-ключевые слова

Верни ОБНОВЛЁННЫЙ JSON профиль в том же формате, что и исходный,
но с обогащёнными полями и добавь поле "enrichment_notes" с кратким объяснением изменений.

ВАЖНО: Верни ТОЛЬКО JSON, без markdown и объяснений."""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=2500,
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    raw = raw.strip()

    try:
        enriched = json.loads(raw)
        if not enriched.get("hidden_patterns") and profile.get("hidden_patterns"):
            enriched["hidden_patterns"] = profile["hidden_patterns"]
        return enriched
    except json.JSONDecodeError:
        profile["enrichment_notes"] = "Обогащение не удалось, используется исходный профиль"
        return profile


# ============================================================
# ИЗВЛЕЧЕНИЕ ТЕКСТА ИЗ PDF
# ============================================================
async def extract_pdf_text(file_bytes: bytes) -> str:
    """Извлекает текст из PDF используя PyMuPDF и pdfplumber как fallback."""
    try:
        import fitz
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        if text.strip():
            return text
    except Exception as e:
        import logging
        logging.warning(f"PyMuPDF failed: {e}")

    try:
        import pdfplumber
        import io
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            text = ""
            for page in pdf.pages:
                text += page.extract_text() or ""
        return text
    except Exception as e:
        import logging
        logging.error(f"pdfplumber failed: {e}")
        return ""

# ============================================================
# ОПРЕДЕЛЕНИЕ ТИПА ВВОДА
# ============================================================
CV_KEYWORDS = [
    "опыт работы", "образование", "навыки", "должность", "компания",
    "университет", "институт", "специальность", "резюме", "достижения",
    "berufserfahrung", "ausbildung", "kenntnisse", "lebenslauf", "arbeitgeber",
    "universität", "hochschule", "fähigkeiten", "tätigkeiten", "abschluss",
    "experience", "education", "skills", "employment", "university",
    "bachelor", "master", "degree", "responsibilities", "achievements",
    "досвід роботи", "освіта", "навички", "посада", "компанія",
    "خبرة", "تعليم", "مهارات", "وظيفة",
]

def is_full_cv(text: str) -> bool:
    if not text or not text.strip():
        return False
    text_lower = text.lower()
    word_count = len(text.split())
    if word_count < 30:
        return False
    keyword_matches = sum(1 for kw in CV_KEYWORDS if kw in text_lower)
    if word_count >= 100 and keyword_matches >= 2:
        return True
    if word_count >= 50 and keyword_matches >= 3:
        return True
    return False
