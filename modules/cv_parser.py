import os
import json
import logging
import asyncio
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

async def parse_cv(cv_text: str, lang: str = "ru") -> dict:
    """
    Парсит резюме и возвращает структурированный профиль.
    Не просто извлекает данные — интерпретирует и находит неочевидные связи.
    """
    lang_name = LANG_NAMES.get(lang, "русском языке")

    prompt = f"""Ты — опытный карьерный консультант и хедхантер со специализацией на рынке труда DACH (Германия, Австрия, Швейцария). 
За твоими плечами — тысячи успешно трудоустроенных кандидатов. Ты умеешь видеть в людях то, что они сами в себе не замечают.

ЯЗЫК ОТВЕТА: Все текстовые поля JSON пиши ИСКЛЮЧИТЕЛЬНО на {lang_name}. 
Это критически важно — кандидат читает на этом языке и не должен видеть текст на других языках.
Исключение: search_queries для Google Maps — только на немецком.

ТВОЯ ЗАДАЧА: Внимательно прочитай резюме и сделай глубокий анализ. Не просто перепиши данные — думай как детектив и стратег одновременно.

ШАГ 1 — ФАКТЫ: Извлеки базовую информацию (имя, локация, опыт, навыки, языки).

ШАГ 2 — ИНТЕРПРЕТАЦИЯ: Что на самом деле умеет этот человек? 
Примеры неочевидных связей:
- Юрист + Python + Prompt Engineering = LegalTech специалист, AI Compliance эксперт
- Врач + менеджмент = Healthcare Operations Manager
- Учитель + публичные выступления = Corporate Trainer, HR Business Partner
- Бухгалтер + Excel + VBA = Financial Automation Specialist

ШАГ 3 — РЫНОК DACH: Где в Германии, Австрии, Швейцарии ищут ИМЕННО такой профиль?
Думай нестандартно:
- Если юрист НЕ немецкого права — это не минус, это плюс для международных компаний, LegalTech стартапов, IT-компаний с compliance отделом
- Ищи компании где уникальный микс навыков кандидата является преимуществом, а не недостатком

ШАГ 4 — УТОЧНЯЮЩИЕ ВОПРОСЫ: Задай 3-5 вопросов которые помогут раскрыть скрытый потенциал.
Хорошие вопросы звучат так:
- "Вы упоминаете что работали с командой — расскажите, каких конкретных результатов вы достигли?"
- "Вы используете Python в работе — для каких задач? Есть примеры автоматизации?"
- Плохой вопрос: "Укажите желаемую зарплату" — слишком банально для первого контакта

РЕЗЮМЕ КАНДИДАТА:
{cv_text}

Отвечай СТРОГО в JSON без markdown блоков и без лишних комментариев:
{{
  "name": "полное имя кандидата",
  "location": "город, страна (как указано в резюме)",
  "experience_years": 0,
  "primary_domain": "основная сфера деятельности (1-3 слова, на {lang_name})",
  "hidden_competencies": [
    "неочевидная компетенция 1 — объясни почему она есть",
    "неочевидная компетенция 2 — объясни почему она есть"
  ],
  "cross_domain_opportunities": [
    "конкретное название должности в DACH которая подходит",
    "ещё одна должность",
    "ещё одна"
  ],
  "skills": ["навык 1", "навык 2", "навык 3"],
  "languages": [
    {{"lang": "DE", "level": "B2"}},
    {{"lang": "EN", "level": "C1"}}
  ],
  "target_companies_dach": [
    "тип компании 1 (например: LegalTech стартапы в Берлине)",
    "тип компании 2",
    "тип компании 3"
  ],
  "search_queries": [
    "поисковый запрос на немецком для Google Maps 1",
    "поисковый запрос на немецком для Google Maps 2",
    "поисковый запрос на немецком для Google Maps 3"
  ],
  "clarifying_questions": [
    "живой конкретный вопрос 1 на {lang_name}",
    "живой конкретный вопрос 2 на {lang_name}",
    "живой конкретный вопрос 3 на {lang_name}"
  ]
}}"""

    try:
        result = await groq_ask_async(prompt)
        result = result.strip()
        if result.startswith("```"):
            result = result.split("```")[1]
            if result.startswith("json"):
                result = result[4:]
        profile = json.loads(result.strip())
        return profile
    except Exception as e:
        logging.error(f"CV Parser error: {e}")
        fallback_questions = {
            "ru": ["Какую должность вы ищете в первую очередь?", "В каком городе Германии вы хотите работать?", "Какой у вас уровень немецкого языка?"],
            "de": ["Welche Position suchen Sie in erster Linie?", "In welcher deutschen Stadt möchten Sie arbeiten?", "Wie ist Ihr Deutschniveau?"],
            "en": ["What position are you primarily looking for?", "Which German city do you want to work in?", "What is your German language level?"],
            "uk": ["Яку посаду ви шукаєте насамперед?", "У якому місті Німеччини ви хочете працювати?", "Який у вас рівень німецької мови?"],
            "ar": ["ما المنصب الذي تبحث عنه في المقام الأول؟", "في أي مدينة ألمانية تريد العمل؟", "ما مستوى لغتك الألمانية؟"],
            "ps": ["تاسو لومړی کوم دنده لټوئ؟", "د جرمني کوم ښار کې کار کول غواړئ؟", "ستاسو د جرمني ژبې کچه څه ده؟"]
        }
        return {
            "name": "Кандидат",
            "location": "",
            "experience_years": 0,
            "primary_domain": "",
            "hidden_competencies": [],
            "cross_domain_opportunities": [],
            "skills": [],
            "languages": [],
            "target_companies_dach": [],
            "search_queries": [],
            "clarifying_questions": fallback_questions.get(lang, fallback_questions["ru"])
        }

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
