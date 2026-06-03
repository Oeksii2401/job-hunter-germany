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

async def parse_cv(cv_text: str, lang: str = "ru") -> dict:
    """
    Парсит резюме и возвращает структурированный профиль.
    Не просто извлекает данные — интерпретирует и находит неочевидные связи.
    """
    prompt = f"""Ты — эксперт по карьерному консультированию для рынка DACH (Германия, Австрия, Швейцария).

ЗАДАЧА: Проанализируй резюме кандидата. Не просто извлекай данные — ИНТЕРПРЕТИРУЙ их и находи неочевидные связи.

АЛГОРИТМ:
1. ИЗВЛЕЧЕНИЕ: имя, локация, опыт (лет), навыки, языки, образование
2. ИНТЕРПРЕТАЦИЯ: какие неочевидные компетенции скрыты за опытом?
3. СВЯЗИ: найди неожиданные комбинации навыков (пример: юрист + Python + Prompt Engineering = LegalTech специалист)
4. РЫНОК DACH: какие профессии и компании в Германии ищут именно такой профиль?
5. ВОПРОСЫ: сформируй 3-5 уточняющих вопросов которые помогут усилить профиль

ВАЖНО для юристов с нестандартным правом:
- Если кандидат юрист НЕ немецкого права — ищи LegalTech компании, международные фирмы, IT компании с юридическим отделом, консалтинг
- Не ограничивайся только адвокатскими конторами

РЕЗЮМЕ:
{cv_text}

Отвечай СТРОГО в JSON (без markdown блоков):
{{
  "name": "имя кандидата",
  "location": "город, страна",
  "experience_years": 0,
  "primary_domain": "основная сфера",
  "hidden_competencies": ["скрытая компетенция 1", "скрытая компетенция 2"],
  "cross_domain_opportunities": ["LegalTech специалист", "IT Compliance Manager"],
  "skills": ["навык 1", "навык 2"],
  "languages": [{{"lang": "DE", "level": "B2"}}, {{"lang": "EN", "level": "C1"}}],
  "target_companies_dach": ["тип компании 1", "тип компании 2"],
  "search_queries": ["запрос для Google Maps 1", "запрос для Google Maps 2"],
  "clarifying_questions": ["вопрос 1", "вопрос 2", "вопрос 3"]
}}"""

    try:
        result = await groq_ask_async(prompt)
        # Убираем возможные markdown блоки
        result = result.strip()
        if result.startswith("```"):
            result = result.split("```")[1]
            if result.startswith("json"):
                result = result[4:]
        profile = json.loads(result.strip())
        return profile
    except Exception as e:
        logging.error(f"CV Parser error: {e}")
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
            "clarifying_questions": ["Какова ваша желаемая должность?", "В каком городе ищете работу?", "Какой уровень немецкого языка?"]
        }

async def extract_pdf_text(file_bytes: bytes) -> str:
    """Извлекает текст из PDF используя PyMuPDF и pdfplumber как fallback."""
    try:
        import fitz  # PyMuPDF
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
