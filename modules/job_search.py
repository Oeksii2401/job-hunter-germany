import os
import json
import logging
import asyncio
import re
import httpx
from groq import Groq

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
GROQ_MODEL = "llama-3.3-70b-versatile"

# Возможные пути карьерных страниц у немецких компаний
CAREER_URL_PATHS = [
    "/karriere",
    "/jobs",
    "/stellenangebote",
    "/career",
    "/careers",
    "/arbeiten-bei-uns",
    "/offene-stellen",
    "/vacancies",
    "/en/careers",
    "/de/karriere",
]


# ============================================================
# ГЕОКОДИРОВАНИЕ
# ============================================================
async def geocode_location(location: str) -> dict:
    """Конвертирует название города в координаты."""
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": location,
        "key": GOOGLE_MAPS_API_KEY
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, timeout=10)
            data = resp.json()
            if data.get("results"):
                loc = data["results"][0]["geometry"]["location"]
                return {"lat": loc["lat"], "lng": loc["lng"]}
    except Exception as e:
        logging.error(f"Geocoding error: {e}")
    # Hannover по умолчанию
    return {"lat": 52.3759, "lng": 9.7320}


# ============================================================
# ПОИСК КОМПАНИЙ ЧЕРЕЗ GOOGLE MAPS
# ============================================================
async def search_companies(query: str, location: str, radius_km: int = 50) -> list:
    """Ищет компании через Google Maps Places API (New)."""
    coords = await geocode_location(location)

    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_MAPS_API_KEY,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.websiteUri"
    }
    body = {
        "textQuery": f"{query} in {location}",
        "locationBias": {
            "circle": {
                "center": {
                    "latitude": coords["lat"],
                    "longitude": coords["lng"]
                },
                "radius": radius_km * 1000
            }
        }
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, json=body, timeout=15)
            data = resp.json()
            places = data.get("places", [])

            companies = []
            for place in places:
                name = place.get("displayName", {}).get("text", "")
                address = place.get("formattedAddress", "")
                website = place.get("websiteUri", "")
                if name:
                    companies.append({
                        "name": name,
                        "address": address,
                        "website": website,
                        "jobs_url": "",
                        "jobs": []
                    })
            return companies
    except Exception as e:
        logging.error(f"Places API error: {e}")
        return []


# ============================================================
# ПОИСК КАРЬЕРНОЙ СТРАНИЦЫ КОМПАНИИ
# ============================================================
async def find_career_page(website: str) -> str:
    """
    Пробует найти карьерную страницу компании.
    Перебирает стандартные пути и возвращает первый рабочий URL.
    """
    if not website:
        return ""

    base = website.rstrip("/")

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=8,
        headers={"User-Agent": "Mozilla/5.0 (compatible; JobHunterBot/1.0)"}
    ) as client:
        for path in CAREER_URL_PATHS:
            url = base + path
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    # Проверяем что страница содержит что-то релевантное
                    text_lower = resp.text.lower()
                    career_signals = [
                        "stellen", "job", "karriere", "bewerbung",
                        "vacancy", "position", "opening", "hiring"
                    ]
                    if any(signal in text_lower for signal in career_signals):
                        return url
            except Exception:
                continue

    return ""


# ============================================================
# ИЗВЛЕЧЕНИЕ ВАКАНСИЙ СО СТРАНИЦЫ
# ============================================================
async def scrape_jobs(career_url: str, cv_profile: dict) -> list:
    """
    Заходит на карьерную страницу и извлекает релевантные вакансии.
    Использует LLM для анализа текста страницы.
    """
    if not career_url:
        return []

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0 (compatible; JobHunterBot/1.0)"}
        ) as client:
            resp = await client.get(career_url)
            if resp.status_code != 200:
                return []
            page_text = resp.text
    except Exception as e:
        logging.warning(f"Scraping error {career_url}: {e}")
        return []

    # Очищаем HTML — убираем теги, оставляем текст
    clean_text = re.sub(r"<[^>]+>", " ", page_text)
    clean_text = re.sub(r"\s+", " ", clean_text).strip()

    # Ограничиваем размер для LLM
    if len(clean_text) > 3000:
        clean_text = clean_text[:3000] + "..."

    # Профиль кандидата для релевантности
    target_roles = cv_profile.get("cross_domain_opportunities", [])
    skills = cv_profile.get("skills", [])
    domain = cv_profile.get("primary_domain", "")

    prompt = f"""Проанализируй текст карьерной страницы немецкой компании.

ПРОФИЛЬ КАНДИДАТА:
- Сфера: {domain}
- Целевые роли: {', '.join(target_roles[:5])}
- Навыки: {', '.join(skills[:8])}

ТЕКСТ СТРАНИЦЫ:
{clean_text}

ЗАДАЧА: Найди вакансии которые ПОДХОДЯТ этому кандидату.
Если вакансий нет или текст нечитаемый — верни пустой массив.

Отвечай ТОЛЬКО в JSON без markdown:
[
  {{
    "title": "название вакансии",
    "requirements": "ключевые требования (1-2 предложения)",
    "match_reason": "почему подходит кандидату (1 предложение)",
    "match_score": 85
  }}
]

Включай только реально найденные вакансии с match_score >= 50.
Максимум 5 вакансий."""

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000,
            ).choices[0].message.content
        )

        result = result.strip()
        # Убираем markdown если есть
        if result.startswith("```"):
            result = result.split("```")[1]
            if result.startswith("json"):
                result = result[4:]
        result = re.sub(r"\s*```$", "", result).strip()

        jobs = json.loads(result)
        if isinstance(jobs, list):
            return jobs

    except Exception as e:
        logging.warning(f"Jobs extraction error: {e}")

    return []


# ============================================================
# ОСНОВНАЯ ФУНКЦИЯ: ПОИСК КОМПАНИЙ С ВАКАНСИЯМИ
# ============================================================
async def find_companies_for_profile(cv_profile: dict, scrape: bool = True) -> list:
    """
    Ищет компании для кандидата на основе его профиля.
    Опционально скрапит карьерные страницы для реальных вакансий.

    Args:
        cv_profile: профиль из cv_parser / cv_analyst
        scrape: искать ли вакансии на сайтах компаний (медленнее, но лучше)

    Returns:
        Список компаний с найденными вакансиями
    """
    location = cv_profile.get("location", "Hannover, Germany")
    search_queries = cv_profile.get("search_queries", [])

    if not search_queries:
        primary_domain = cv_profile.get("primary_domain", "")
        search_queries = [primary_domain] if primary_domain else ["Unternehmen Hannover"]

    # 1. Собираем компании по всем запросам
    all_companies = []
    seen_names = set()

    for query in search_queries[:3]:
        companies = await search_companies(query, location, radius_km=50)
        for company in companies:
            if company["name"] not in seen_names:
                seen_names.add(company["name"])
                all_companies.append(company)

    # Ограничиваем до 10
    all_companies = all_companies[:10]

    if not scrape:
        # Без скрапинга — просто проставляем стандартный jobs_url
        for company in all_companies:
            if company.get("website"):
                company["jobs_url"] = company["website"].rstrip("/") + "/karriere"
        return all_companies

    # 2. Для каждой компании ищем карьерную страницу и вакансии
    async def enrich_company(company: dict) -> dict:
        website = company.get("website", "")
        if not website:
            return company

        # Ищем карьерную страницу
        career_url = await find_career_page(website)
        company["jobs_url"] = career_url or (website.rstrip("/") + "/karriere")

        # Скрапим вакансии если нашли страницу
        if career_url:
            jobs = await scrape_jobs(career_url, cv_profile)
            company["jobs"] = jobs
        else:
            company["jobs"] = []

        return company

    # Запускаем параллельно для скорости (но не более 5 одновременно)
    semaphore = asyncio.Semaphore(5)

    async def enrich_with_limit(company):
        async with semaphore:
            return await enrich_company(company)

    enriched = await asyncio.gather(
        *[enrich_with_limit(c) for c in all_companies],
        return_exceptions=True
    )

    # Фильтруем ошибки
    result = []
    for item in enriched:
        if isinstance(item, dict):
            result.append(item)

    return result


# ============================================================
# ФОРМАТИРОВАНИЕ РЕЗУЛЬТАТОВ ДЛЯ ЧАТА
# ============================================================
def format_companies_message(companies: list, lang: str = "ru") -> str:
    """Форматирует список компаний для показа в чате."""
    if not companies:
        return "😔 Компании не найдены. Попробуем расширить поиск."

    msg = f"🏢 **Найдено компаний: {len(companies)}**\n\n"

    for i, company in enumerate(companies, 1):
        name = company.get("name", "")
        address = company.get("address", "")
        website = company.get("website", "")
        jobs_url = company.get("jobs_url", "")
        jobs = company.get("jobs", [])

        msg += f"**{i}. {name}**\n"
        if address:
            msg += f"  📍 {address}\n"
        if website:
            msg += f"  🌐 {website}\n"
        if jobs_url and jobs_url != website:
            msg += f"  💼 {jobs_url}\n"

        # Найденные вакансии
        if jobs:
            msg += f"  📋 **Открытые вакансии ({len(jobs)}):**\n"
            for job in jobs[:3]:
                score = job.get("match_score", 0)
                title = job.get("title", "")
                reason = job.get("match_reason", "")
                score_icon = "🟢" if score >= 75 else "🟡" if score >= 50 else "🔴"
                msg += f"    {score_icon} {title} — {reason}\n"

        msg += "\n"

    return msg