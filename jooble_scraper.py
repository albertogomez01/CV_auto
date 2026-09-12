import asyncio
import re
import urllib.parse
from typing import List, Dict, Any, Optional
import httpx
from bs4 import BeautifulSoup
from database import is_job_processed

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Referer": "https://es.jooble.org/"
}

def extract_jooble_id(url: str) -> str:
    """Extracts unique ID from Jooble URL."""
    match = re.search(r'desc/(-?\d+)', url)
    if match:
        return f"jooble_{match.group(1)}"
    return f"jooble_{abs(hash(url))}"

async def search_jooble(keywords: str = "", location: str = "", max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
    """Performs fast async HTTP scraping on Jooble Spain (es.jooble.org)."""
    jobs = []
    q_param = urllib.parse.quote(keywords)
    l_param = urllib.parse.quote(location) if location else ""
    url = f"https://es.jooble.org/SearchResult?p=1&rgns={l_param}&kw={q_param}"

    try:
        async with httpx.AsyncClient(headers=DEFAULT_HEADERS, timeout=10.0, follow_redirects=True) as client:
            res = await client.get(url)
            if res.status_code != 200:
                print(f"[Jooble Scraper] Status code: {res.status_code}")
                return []

            soup = BeautifulSoup(res.text, "html.parser")
            # Jooble job cards query
            cards = soup.select("article, div[data-test-name='job-card'], div.card, div._150b0")
            if not cards:
                cards = soup.select("a[href*='/desc/']")

            seen_links = set()
            for card in cards[:max_results * 2]:
                link_el = card if card.name == 'a' else card.select_one("a[href*='/desc/'], a[href*='jooble.org'], h2 a, a[data-test-name='job-title']")
                if not link_el:
                    continue

                link = link_el.get("href", "")
                if not link:
                    continue

                if not link.startswith("http"):
                    link = f"https://es.jooble.org{link}"

                if link in seen_links:
                    continue
                seen_links.add(link)

                title = link_el.get_text(strip=True) or "Vacante en Jooble"
                if len(title) < 3 or "Jooble" in title:
                    continue

                job_id = extract_jooble_id(link)
                if is_job_processed(job_id):
                    continue

                company = "Empresa en Jooble"
                salary = "Salario no especificado"
                job_loc = location if location else "España"

                if card.name != 'a':
                    comp_el = card.select_one("[class*='company'], [class*='Company'], div._47d15, span._3673b")
                    if comp_el and comp_el.get_text(strip=True):
                        company = comp_el.get_text(strip=True)

                    sal_el = card.select_one("[class*='salary'], [class*='Salary'], div._43152")
                    if sal_el and sal_el.get_text(strip=True):
                        salary = sal_el.get_text(strip=True)

                    loc_el = card.select_one("[class*='location'], [class*='Location'], div._13328")
                    if loc_el and loc_el.get_text(strip=True):
                        job_loc = loc_el.get_text(strip=True)

                modality = "Presencial"
                if "remoto" in title.lower() or "remoto" in job_loc.lower():
                    modality = "En remoto"

                jobs.append({
                    "id": job_id,
                    "title": title,
                    "company": company,
                    "link": link,
                    "salary": salary,
                    "location": job_loc,
                    "modality": modality,
                    "platform": "Jooble",
                    "description": f"Vacante de empleo en Jooble: {title} en {company}.",
                    "killer_questions": []
                })

                if len(jobs) >= max_results:
                    break
    except Exception as e:
        print(f"[Jooble Scraper] Error: {e}")

    return jobs
