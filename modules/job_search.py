import os
import json
import logging
import asyncio
import httpx

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

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
            if data["results"]:
                loc = data["results"][0]["geometry"]["location"]
                return {"lat": loc["lat"], "lng": loc["lng"]}
    except Exception as e:
        logging.error(f"Geocoding error: {e}")
    # Hannover по умолчанию
    return {"lat": 52.3759, "lng": 9.7320}

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
                        "jobs_url": f"{website.rstrip('/')}/karriere" if website else ""
                    })
            return companies
    except Exception as e:
        logging.error(f"Places API error: {e}")
        return []

async def find_companies_for_profile(cv_profile: dict) -> list:
    """Ищет компании для кандидата на основе его профиля."""
    location = cv_profile.get("location", "Hannover, Germany")
    search_queries = cv_profile.get("search_queries", [])
    
    if not search_queries:
        primary_domain = cv_profile.get("primary_domain", "")
        search_queries = [primary_domain] if primary_domain else ["Unternehmen Hannover"]
    
    all_companies = []
    seen_names = set()
    
    for query in search_queries[:3]:  # максимум 3 запроса
        companies = await search_companies(query, location, radius_km=50)
        for company in companies:
            if company["name"] not in seen_names:
                seen_names.add(company["name"])
                all_companies.append(company)
    
    return all_companies[:10]  # максимум 10 компаний
