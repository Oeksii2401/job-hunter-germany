import os
import json
import logging
import asyncio
import re
from groq import Groq

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
GROQ_MODEL = "llama-3.3-70b-versatile"

# ============================================================
# ЯЗЫКОВЫЕ НАСТРОЙКИ
# ============================================================
LANG_NAMES = {
    "ru": "русском языке",
    "de": "deutscher Sprache",
    "en": "English",
    "uk": "українській мові",
    "ar": "اللغة العربية",
    "ps": "پښتو ژبه"
}

# ============================================================
# БАЗА БАРЬЕРОВ ПО ПРОФЕССИЯМ В ГЕРМАНИИ
# ============================================================
PROFESSION_BARRIERS = {
    "юрист": {
        "keywords": [
            "юрист", "lawyer", "rechtsanwalt", "attorney", "правовед",
            "legal", "право", "jura", "jurist", "advokat", "адвокат",
            # украинский
            "юрист", "адвокат", "правник",
            # арабский (латинизация)
            "محامي", "قانون", "حقوق",
        ],
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
        "keywords": [
            "врач", "doctor", "arzt", "медик", "physician", "surgeon",
            "хирург", "терапевт", "педиатр", "medicina", "медицина",
            # украинский
            "лікар", "медик",
            # арабский
            "طبيب", "دكتور", "طب",
        ],
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
        "keywords": [
            "учитель", "teacher", "lehrer", "педагог", "преподаватель",
            "educator", "schullehrer",
            # украинский
            "вчитель", "викладач",
            # арабский
            "معلم", "مدرس",
        ],
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
        "keywords": [
            "архитектор", "architect", "architekt", "проектировщик", "градостроитель",
            # украинский
            "архітектор",
            # арабский
            "مهندس معماري", "معماري",
        ],
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
        "keywords": [
            "инженер", "engineer", "ingenieur", "механик", "электрик", "конструктор",
            # украинский
            "інженер",
            # арабский
            "مهندس",
        ],
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
        "keywords": [
            "бухгалтер", "accountant", "buchhalter", "финансист", "аудитор",
            "steuerberater", "налоговый",
            # украинский
            "бухгалтер", "фінансист",
            # арабский
            "محاسب", "مالية",
        ],
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
        "keywords": [
            "психолог", "psychologist", "psychologe", "психотерапевт", "therapist",
            # украинский
            "психолог", "психотерапевт",
            # арабский
            "طبيب نفسي", "نفسي",
        ],
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
# КЛЮЧЕВЫЕ СЛОВА ДЛЯ ОПРЕДЕЛЕНИЯ ТИПА ТЕКСТА
# ============================================================
CV_KEYWORDS = [
    # Русский
    "опыт работы", "образование", "навыки", "должность", "компания",
    "университет", "институт", "специальность", "резюме", "достижения",
    # Немецкий
    "berufserfahrung", "ausbildung", "kenntnisse", "lebenslauf", "arbeitgeber",
    "universität", "hochschule", "fähigkeiten", "tätigkeiten", "abschluss",
    # Английский
    "experience", "education", "skills", "employment", "university",
    "bachelor", "master", "degree", "responsibilities", "achievements",
    # Украинский
    "досвід роботи", "освіта", "навички", "посада", "компанія",
    # Арабский
    "خبرة", "تعليم", "مهارات", "وظيفة",
]


# ============================================================
# ОПРЕДЕЛЕНИЕ ТИПА ВВОДА
# ============================================================
def is_full_cv(text: str) -> bool:
    """
    Определяет является ли текст полноценным резюме или просто кратким запросом.
    Логика: если текст длинный И содержит ключевые слова резюме — это резюме.
    """
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


# ============================================================
# ОПРЕДЕЛЕНИЕ ПРОФЕССИИ С БАРЬЕРАМИ
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
# СКРЫТЫЕ ПАТТЕРНЫ НАВЫКОВ
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
        "skills": ["lawyer", "python"],
        "label": "LegalTech Specialist",
        "description": "Rare combination: legal knowledge + programming = LegalTech developer or legal process automation consultant"
    },
    {
        "skills": ["legal", "compliance"],
        "label": "Compliance Expert",
        "description": "Legal background + compliance experience = ready Compliance Manager without German license"
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
        "skills": ["doctor", "python"],
        "label": "Medical Data Scientist",
        "description": "Medical background + programming = medical data scientist or MedTech specialist"
    },
    {
        "skills": ["финансы", "python"],
        "label": "FinTech Developer",
        "description": "Финансовая экспертиза + программирование = FinTech специалист"
    },
    {
        "skills": ["finance", "python"],
        "label": "FinTech Developer",
        "description": "Financial expertise + programming = FinTech specialist"
    },
    {
        "skills": ["учитель", "онлайн"],
        "label": "E-Learning Specialist",
        "description": "Педагогика + онлайн-опыт = разработчик e-learning контента и учебных программ"
    },
    {
        "skills": ["teacher", "online"],
        "label": "E-Learning Specialist",
        "description": "Pedagogy + online experience = e-learning content developer"
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
        "skills": ["engineer", "python"],
        "label": "Industrial Automation Engineer",
        "description": "Engineering background + programming = industrial automation and IoT specialist"
    },
    {
        "skills": ["маркетинг", "ai"],
        "label": "AI Marketing Specialist",
        "description": "Маркетинговый опыт + AI-инструменты = очень востребованная роль в 2024-2025"
    },
    {
        "skills": ["marketing", "ai"],
        "label": "AI Marketing Specialist",
        "description": "Marketing experience + AI tools = highly demanded role in 2024-2025"
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
    """Убирает markdown-обёртки из JSON ответа."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


# ============================================================
# ОСНОВНОЙ ПАРСЕР CV
# ============================================================
async def parse_cv(cv_text: str, lang: str = "ru") -> dict:
    """
    Парсит CV и возвращает структурированный профиль.
    Учитывает язык кандидата, профессиональные барьеры и скрытые паттерны.
    """
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

    prompt = f"""Ты — опытный карьерный консультант и хедхантер со специализацией на рынке труда DACH (Германия, Австрия, Швейцария).
За твоими плечами — тысячи успешно трудоустроенных кандидатов. Ты умеешь видеть в людях то, что они сами в себе не замечают.

ЯЗЫК ОТВЕТА: Все текстовые поля JSON пиши ИСКЛЮЧИТЕЛЬНО на {lang_name}.
Это критически важно — кандидат читает на этом языке и не должен видеть текст на других языках.
Исключение: search_queries для Google Maps — только на немецком.

{barriers_text}

ТВОЯ ЗАДАЧА: Внимательно прочитай резюме и сделай глубокий анализ. Думай как детектив и стратег одновременно.

ШАГ 1 — ФАКТЫ: Извлеки базовую информацию (имя, локация, опыт, навыки, языки).

ШАГ 2 — ИНТЕРПРЕТАЦИЯ: Что на самом деле умеет этот человек?
Примеры неочевидных связей:
- Юрист + Python + Prompt Engineering = LegalTech специалист, AI Compliance эксперт
- Врач + менеджмент = Healthcare Operations Manager
- Учитель + публичные выступления = Corporate Trainer, HR Business Partner
- Бухгалтер + Excel + VBA = Financial Automation Specialist

ШАГ 3 — РЫНОК DACH: Где в Германии, Австрии, Швейцарии ищут ИМЕННО такой профиль?
Думай нестандартно:
- Если юрист НЕ немецкого права — это не минус, это плюс для международных компаний, LegalTech стартапов
- Ищи компании где уникальный микс навыков кандидата является преимуществом

ШАГ 4 — УТОЧНЯЮЩИЕ ВОПРОСЫ: Задай 3-5 конкретных вопросов которые помогут раскрыть скрытый потенциал.
Хорошие вопросы:
- "Вы упоминаете что работали с командой — расскажите, каких конкретных результатов достигли?"
- "Вы используете Python в работе — для каких задач? Есть примеры автоматизации?"
Плохой вопрос: "Укажите желаемую зарплату" — слишком банально

РЕЗЮМЕ / ПРОФИЛЬ КАНДИДАТА:
{cv_text}

Отвечай СТРОГО в JSON без markdown и без лишних комментариев:
{{
  "name": "полное имя кандидата (или пустая строка если не указано)",
  "location": "город, страна (как указано или пустая строка)",
  "experience_years": 0,
  "primary_domain": "основная сфера деятельности (1-3 слова)",
  "hidden_competencies": [
    "неочевидная компетенция 1 — объясни почему она есть",
    "неочевидная компетенция 2 — объясни почему она есть"
  ],
  "cross_domain_opportunities": [
    "конкретное название должности в DACH",
    "ещё одна должность"
  ],
  "skills": ["навык 1", "навык 2", "навык 3"],
  "languages": [
    {{"lang": "DE", "level": "B2"}},
    {{"lang": "EN", "level": "C1"}}
  ],
  "target_companies_dach": [
    "тип компании 1 (например: LegalTech стартапы в Берлине)",
    "тип компании 2"
  ],
  "search_queries": [
    "поисковый запрос на немецком для Google Maps 1",
    "поисковый запрос на немецком для Google Maps 2",
    "поисковый запрос на немецком для Google Maps 3"
  ],
  "barriers": [],
  "workarounds": [],
  "clarifying_questions": [
    "живой конкретный вопрос 1",
    "живой конкретный вопрос 2",
    "живой конкретный вопрос 3"
  ]
}}"""

    # Fallback вопросы на всех языках
    fallback_questions = {
        "ru": [
            "Есть ли у вас опыт работы с немецкими компаниями или в немецкоязычной среде?",
            "Какой у вас текущий уровень немецкого языка?",
            "Рассматриваете ли вы переобучение или дополнительную сертификацию в Германии?",
            "Есть ли у вас опыт в сферах, не отражённых в CV (волонтёрство, проекты, фриланс)?",
            "В каком городе или регионе Германии вы ищете работу?"
        ],
        "de": [
            "Haben Sie Erfahrung mit deutschen Unternehmen oder in deutschsprachigen Umgebungen?",
            "Wie ist Ihr aktuelles Deutschniveau?",
            "Erwägen Sie eine Umschulung oder zusätzliche Zertifizierung in Deutschland?",
            "Haben Sie Erfahrungen, die nicht im Lebenslauf stehen (Ehrenamt, Projekte, Freelance)?",
            "In welcher Stadt oder Region Deutschlands suchen Sie Arbeit?"
        ],
        "en": [
            "Do you have experience working with German companies or in a German-speaking environment?",
            "What is your current level of German?",
            "Are you open to retraining or additional certification in Germany?",
            "Do you have experience not reflected in your CV (volunteering, projects, freelance)?",
            "Which city or region of Germany are you looking to work in?"
        ],
        "uk": [
            "Чи є у вас досвід роботи з німецькими компаніями або в німецькомовному середовищі?",
            "Який у вас поточний рівень німецької мови?",
            "Чи розглядаєте ви перенавчання або додаткову сертифікацію в Німеччині?",
            "Чи є у вас досвід, не відображений у резюме (волонтерство, проекти, фріланс)?",
            "У якому місті або регіоні Німеччини ви шукаєте роботу?"
        ],
        "ar": [
            "هل لديك خبرة في العمل مع شركات ألمانية أو في بيئة ناطقة بالألمانية؟",
            "ما مستوى اللغة الألمانية الحالي لديك؟",
            "هل تفكر في إعادة التدريب أو الحصول على شهادات إضافية في ألمانيا؟",
            "هل لديك خبرة غير مذكورة في السيرة الذاتية (تطوع، مشاريع، عمل حر)؟",
            "في أي مدينة أو منطقة في ألمانيا تبحث عن عمل؟"
        ],
        "ps": [
            "آیا تاسو د جرمني شرکتونو سره یا د جرمني ژبې چاپیریال کې د کار تجربه لرئ؟",
            "ستاسو د جرمني ژبې اوسنی کچه څه ده؟",
            "آیا تاسو د جرمني کې د بیا روزنې یا اضافي سند ترلاسه کولو ته چمتو یاست؟",
            "آیا تاسو داسې تجربه لرئ چې ستاسو د CV ​​​​کې نه وي (داوطلبانه کار، پروژې، فریلانس)?",
            "تاسو د جرمني کوم ښار یا سیمه کې کار لټوئ؟"
        ]
    }

    try:
        result = await groq_ask_async(prompt)
        result = clean_json(result)
        profile = json.loads(result)

        # 2. Подставляем барьеры если LLM их не нашла
        if not profile.get("barriers"):
            profile["barriers"] = barriers_info
        if not profile.get("workarounds"):
            profile["workarounds"] = workarounds_info

        # 3. Ищем скрытые паттерны
        hidden_patterns = detect_hidden_patterns(cv_text, profile)
        if hidden_patterns:
            profile["hidden_patterns"] = [
                {"label": p["label"], "description": p["description"]}
                for p in hidden_patterns
            ]
            for p in hidden_patterns:
                roles = profile.setdefault("cross_domain_opportunities", [])
                if p["label"] not in roles:
                    roles.append(p["label"])
        else:
            profile["hidden_patterns"] = []

        # 4. Метаданные
        profile["detected_professions"] = detected_professions
        profile["has_barriers"] = len(barriers_info) > 0

        return profile

    except Exception as e:
        logging.error(f"CV Parser error: {e}")
        return {
            "name": "",
            "location": "",
            "experience_years": 0,
            "primary_domain": "",
            "hidden_competencies": [],
            "cross_domain_opportunities": [],
            "skills": [],
            "languages": [],
            "target_companies_dach": [],
            "search_queries": [],
            "barriers": barriers_info,
            "workarounds": workarounds_info,
            "hidden_patterns": [],
            "detected_professions": detected_professions,
            "has_barriers": len(barriers_info) > 0,
            "clarifying_questions": fallback_questions.get(lang, fallback_questions["ru"])
        }


# ============================================================
# ФОРМАТИРОВАНИЕ ПРОФИЛЯ ДЛЯ ЧАТА
# ============================================================
def format_profile_message(profile: dict, lang: str = "ru") -> str:
    """Форматирует профиль для показа пользователю в чате."""

    name = profile.get("name", "Кандидат")
    primary_domain = profile.get("primary_domain", "")
    cross_domain = profile.get("cross_domain_opportunities", [])
    barriers = profile.get("barriers", [])
    workarounds = profile.get("workarounds", [])
    hidden_patterns = profile.get("hidden_patterns", [])
    hidden_competencies = profile.get("hidden_competencies", [])
    skills = profile.get("skills", [])
    languages = profile.get("languages", [])
    target_companies = profile.get("target_companies_dach", [])

    msg = f"✅ **Профиль создан: {name}**\n\n"

    if primary_domain:
        msg += f"🎯 **Сфера:** {primary_domain}\n\n"

    # Скрытые компетенции от LLM
    if hidden_competencies:
        msg += "🔍 **Скрытые компетенции:**\n"
        for hc in hidden_competencies[:3]:
            msg += f"  • {hc}\n"
        msg += "\n"

    # Барьеры — честно и прямо
    if barriers:
        msg += "⚠️ **Важные барьеры для трудоустройства:**\n"
        for b in barriers:
            msg += f"  • {b}\n"
        msg += "\n"

    # Workarounds
    if workarounds:
        msg += "✅ **Обходные пути и возможности:**\n"
        for w in workarounds[:5]:
            msg += f"  • {w}\n"
        msg += "\n"

    # Скрытые паттерны из базы
    if hidden_patterns:
        msg += "🌟 **Уникальные комбинации навыков:**\n"
        for p in hidden_patterns:
            msg += f"  **{p['label']}** — {p['description']}\n"
        msg += "\n"

    # Целевые роли
    if cross_domain:
        msg += "🇩🇪 **Целевые роли в DACH:**\n"
        for role in cross_domain[:6]:
            msg += f"  • {role}\n"
        msg += "\n"

    # Типы компаний
    if target_companies:
        msg += "🏢 **Где искать:**\n"
        for c in target_companies[:4]:
            msg += f"  • {c}\n"
        msg += "\n"

    # Навыки и языки
    if skills:
        msg += f"🛠️ **Ключевые навыки:** {', '.join(skills[:8])}\n"

    if languages:
        lang_list = [f"{l.get('lang', '')} ({l.get('level', '')})" for l in languages]
        msg += f"🗣️ **Языки:** {', '.join(lang_list)}\n"

    return msg


# ============================================================
# ОБНОВЛЕНИЕ ПРОФИЛЯ ПОСЛЕ ДИАЛОГА
# ============================================================
async def enrich_profile(profile: dict, qa_pairs: list, lang: str = "ru") -> dict:
    """
    Обновляет и усиливает профиль после диалога с кандидатом.
    qa_pairs: список {"question": "...", "answer": "..."}
    """
    lang_name = LANG_NAMES.get(lang, "русском языке")

    qa_text = "\n".join([
        f"Q: {pair.get('question', '')}\nA: {pair.get('answer', '')}"
        for pair in qa_pairs
    ])

    prompt = f"""Ты — опытный карьерный консультант.
На основе исходного профиля CV и ответов кандидата — создай УСИЛЕННЫЙ финальный профиль.

ЯЗЫК ОТВЕТА: Все текстовые поля JSON пиши на {lang_name}.
Исключение: search_queries — только на немецком.

ИСХОДНЫЙ ПРОФИЛЬ:
{json.dumps(profile, ensure_ascii=False, indent=2)}

ДИАЛОГ С КАНДИДАТОМ:
{qa_text}

ЗАДАЧА:
1. Переоцени профиль с учётом новой информации
2. Найди новые возможности, которые не были видны из CV
3. Скорректируй целевые роли и стратегию
4. Усиль позиционирование для немецкого рынка
5. Обнови search_queries для поиска компаний
6. Добавь поле "enrichment_notes" — краткое объяснение изменений

Верни ОБНОВЛЁННЫЙ JSON профиль в том же формате, что и исходный.
ВАЖНО: Верни ТОЛЬКО JSON, без markdown и объяснений."""

    try:
        result = await groq_ask_async(prompt)
        result = clean_json(result)
        enriched = json.loads(result)

        # Сохраняем скрытые паттерны из оригинала если LLM их потеряла
        if not enriched.get("hidden_patterns") and profile.get("hidden_patterns"):
            enriched["hidden_patterns"] = profile["hidden_patterns"]
        if not enriched.get("barriers") and profile.get("barriers"):
            enriched["barriers"] = profile["barriers"]
        if not enriched.get("workarounds") and profile.get("workarounds"):
            enriched["workarounds"] = profile["workarounds"]

        return enriched

    except Exception as e:
        logging.error(f"Enrich profile error: {e}")
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
        logging.error(f"pdfplumber failed: {e}")
        return ""