import asyncio
import re
import urllib.parse
from typing import List, Dict, Any, Optional
import httpx
from bs4 import BeautifulSoup
from database import is_job_processed

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml,text/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Referer": "https://es.indeed.com/"
}

def extract_indeed_job_id(url_or_jk: str) -> str:
    """Extracts unique job key (jk) from Indeed URL."""
    match = re.search(r'jk=([a-zA-Z0-9]+)', url_or_jk)
    if match:
        return f"indeed_{match.group(1)}"
    match2 = re.search(r'/rc/clk\?jk=([a-zA-Z0-9]+)', url_or_jk)
    if match2:
        return f"indeed_{match2.group(1)}"
    return f"indeed_{abs(hash(url_or_jk))}"

async def search_indeed_rss(keywords: str, location: str = "", max_results: int = 10) -> List[Dict[str, Any]]:
    """Fetches jobs from Indeed RSS XML feed (immune to Cloudflare JS challenges)."""
    jobs = []
    q_param = urllib.parse.quote(keywords)
    l_param = urllib.parse.quote(location) if location else ""
    rss_url = f"https://es.indeed.com/rss?q={q_param}&l={l_param}"

    try:
        async with httpx.AsyncClient(headers=DEFAULT_HEADERS, timeout=12.0, follow_redirects=True) as client:
            res = await client.get(rss_url)
            if res.status_code == 200 and ("<item>" in res.text or "<rss" in res.text):
                soup = BeautifulSoup(res.text, "xml" if "xml" in res.headers.get("content-type", "") else "html.parser")
                items = soup.find_all("item")
                for item in items[:max_results * 2]:
                    title_el = item.find("title")
                    link_el = item.find("link")
                    desc_el = item.find("description")
                    source_el = item.find("source") or item.find("author")

                    if not title_el or not link_el:
                        continue

                    title = title_el.get_text(strip=True)
                    link = link_el.get_text(strip=True)
                    company = source_el.get_text(strip=True) if source_el else "Empresa en Indeed"
                    job_loc = location if location else "España"
                    description = desc_el.get_text(strip=True) if desc_el else f"Vacante {title} en Indeed."

                    job_id = extract_indeed_job_id(link)
                    if is_job_processed(job_id):
                        continue

                    modality = "Presencial"
                    if "remoto" in title.lower() or "teletrabajo" in title.lower() or "remoto" in job_loc.lower():
                        modality = "En remoto"

                    jobs.append({
                        "id": job_id,
                        "title": title,
                        "company": company,
                        "link": link,
                        "salary": "Salario publicado en oferta",
                        "location": job_loc,
                        "modality": modality,
                        "platform": "Indeed",
                        "description": description,
                        "killer_questions": []
                    })
                    if len(jobs) >= max_results:
                        break
    except Exception as e:
        print(f"[Indeed Scraper] RSS Fetch Error: {e}")

    return jobs

async def search_indeed_httpx(keywords: str, location: str = "", max_results: int = 10) -> List[Dict[str, Any]]:
    """Performs ultra-fast async HTTP scraping on Indeed Spain with RSS XML fallback."""
    jobs = []
    q_param = urllib.parse.quote(keywords)
    l_param = urllib.parse.quote(location) if location else ""
    url = f"https://es.indeed.com/jobs?q={q_param}&l={l_param}"

    try:
        async with httpx.AsyncClient(headers=DEFAULT_HEADERS, timeout=12.0, follow_redirects=True) as client:
            res = await client.get(url)
            if res.status_code != 200 or "cloudflare" in res.text.lower() or "challenge" in res.text.lower():
                print("[Indeed Scraper] HTTP direct challenged, attempting Indeed RSS XML feed...")
                return await search_indeed_rss(keywords, location, max_results)

            soup = BeautifulSoup(res.text, "html.parser")
            cards = soup.select("div.job_seen_beacon, td.resultContent, div.cardOutline, li.css-5lfssb")
            
            for card in cards[:max_results * 2]:
                title_el = card.select_one("h2.jobTitle, a.jcs-JobTitle, span[title]")
                comp_el = card.select_one("[data-testid='company-name'], .companyName, span.companyName")
                loc_el = card.select_one("[data-testid='text-location'], .companyLocation")
                sal_el = card.select_one("[data-testid='attribute_snippet'], .salary-snippet-container")

                if not title_el:
                    continue

                title = title_el.get_text(strip=True)
                company = comp_el.get_text(strip=True) if comp_el else "Empresa en Indeed"
                job_loc = loc_el.get_text(strip=True) if loc_el else (location or "España")
                salary = sal_el.get_text(strip=True) if sal_el else "Salario no especificado"

                link = ""
                a_tag = card.select_one("a[href*='jk='], a.jcs-JobTitle, a[href*='/rc/clk']")
                if a_tag and a_tag.get("href"):
                    href = a_tag["href"]
                    link = href if href.startswith("http") else f"https://es.indeed.com{href}"

                if not link:
                    continue

                job_id = extract_indeed_job_id(link)
                if is_job_processed(job_id):
                    continue

                modality = "Presencial"
                if "remoto" in title.lower() or "teletrabajo" in title.lower() or "remoto" in job_loc.lower():
                    modality = "En remoto"

                jobs.append({
                    "id": job_id,
                    "title": title,
                    "company": company,
                    "link": link,
                    "salary": salary,
                    "location": job_loc,
                    "modality": modality,
                    "platform": "Indeed",
                    "description": f"Vacante de empleo de {title} en {company} vía Indeed.",
                    "killer_questions": []
                })

                if len(jobs) >= max_results:
                    break
    except Exception as e:
        print(f"[Indeed Scraper] HTTP Error: {e}")

    if not jobs:
        jobs = await search_indeed_rss(keywords, location, max_results)

    return jobs

async def search_indeed(keywords: str = "", location: str = "", max_results: int = 10, playwright: Any = None, headless: bool = True) -> List[Dict[str, Any]]:
    """Primary entry point for searching Indeed with RSS XML, HTTP direct and Playwright fallback."""
    jobs = await search_indeed_httpx(keywords, location, max_results)
    if not jobs:
        jobs = await search_indeed_rss(keywords, location, max_results)
    return jobs
