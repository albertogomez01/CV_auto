import asyncio
import re
import urllib.parse
from typing import List, Dict, Any, Optional
import httpx
from bs4 import BeautifulSoup
from database import is_job_processed

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9",
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

async def search_indeed_playwright(keywords: str, location: str = "", max_results: int = 10, playwright: Any = None, skip_processed: bool = False) -> List[Dict[str, Any]]:
    """Fetches jobs from Indeed using Playwright fast DOM extraction."""
    jobs = []
    q_param = urllib.parse.quote(keywords)
    l_param = urllib.parse.quote(location) if location else ""
    url = f"https://es.indeed.com/jobs?q={q_param}&l={l_param}"

    if not playwright:
        return []

    try:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            locale="es-ES"
        )
        page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=12000)
        await page.wait_for_timeout(1000)

        card_items = await page.evaluate("""
            () => {
                const results = [];
                const cardElements = document.querySelectorAll('div.job_seen_beacon, td.resultContent, div.cardOutline, li.css-5lfssb, [class*="job_seen"]');
                for (const card of cardElements) {
                    const titleEl = card.querySelector('h2.jobTitle, a.jcs-JobTitle, span[title], a[data-jk]');
                    const compEl = card.querySelector('[data-testid="company-name"], .companyName, [class*="company"]');
                    const locEl = card.querySelector('[data-testid="text-location"], .companyLocation, [class*="location"]');
                    const aTag = card.querySelector('a[href*="jk="], a.jcs-JobTitle, a[href*="/rc/clk"], a[href*="/pagead/"]');
                    
                    if (titleEl && aTag) {
                        let href = aTag.href;
                        if (!href.startsWith('http')) href = 'https://es.indeed.com' + href;
                        const title = titleEl.innerText ? titleEl.innerText.trim() : '';
                        const company = compEl && compEl.innerText ? compEl.innerText.trim() : 'Empresa en Indeed';
                        const loc = locEl && locEl.innerText ? locEl.innerText.trim() : 'España';
                        if (title.length > 2) {
                            results.push({ title, company, location: loc, link: href });
                        }
                    }
                }
                return results;
            }
        """)
        await browser.close()

        for item in card_items[:max_results * 2]:
            link = item["link"]
            job_id = extract_indeed_job_id(link)
            if skip_processed and is_job_processed(job_id):
                continue

            jobs.append({
                "id": job_id,
                "title": item["title"],
                "company": item["company"],
                "link": link,
                "salary": "Salario no especificado",
                "location": item.get("location", location or "España"),
                "modality": "Presencial",
                "platform": "Indeed",
                "description": f"Vacante de empleo de {item['title']} en {item['company']} vía Indeed.",
                "killer_questions": []
            })
            if len(jobs) >= max_results:
                break
    except Exception as e:
        print(f"[Indeed Scraper] Playwright Error: {e}")

    return jobs

async def search_indeed_httpx(keywords: str, location: str = "", max_results: int = 10, skip_processed: bool = False) -> List[Dict[str, Any]]:
    """Performs HTTP scraping on Indeed Spain."""
    jobs = []
    q_param = urllib.parse.quote(keywords)
    l_param = urllib.parse.quote(location) if location else ""
    url = f"https://es.indeed.com/jobs?q={q_param}&l={l_param}"

    try:
        async with httpx.AsyncClient(headers=DEFAULT_HEADERS, timeout=10.0, follow_redirects=True) as client:
            res = await client.get(url)
            if res.status_code == 200 and "cloudflare" not in res.text.lower():
                soup = BeautifulSoup(res.text, "html.parser")
                cards = soup.select("div.job_seen_beacon, td.resultContent, div.cardOutline, li.css-5lfssb")
                
                for card in cards[:max_results * 2]:
                    title_el = card.select_one("h2.jobTitle, a.jcs-JobTitle, span[title]")
                    comp_el = card.select_one("[data-testid='company-name'], .companyName, span.companyName")
                    loc_el = card.select_one("[data-testid='text-location'], .companyLocation")

                    if not title_el:
                        continue

                    title = title_el.get_text(strip=True)
                    company = comp_el.get_text(strip=True) if comp_el else "Empresa en Indeed"
                    job_loc = loc_el.get_text(strip=True) if loc_el else (location or "España")

                    a_tag = card.select_one("a[href*='jk='], a.jcs-JobTitle, a[href*='/rc/clk']")
                    if not a_tag or not a_tag.get("href"):
                        continue
                    
                    href = a_tag["href"]
                    link = href if href.startswith("http") else f"https://es.indeed.com{href}"
                    job_id = extract_indeed_job_id(link)
                    if skip_processed and is_job_processed(job_id):
                        continue

                    jobs.append({
                        "id": job_id,
                        "title": title,
                        "company": company,
                        "link": link,
                        "salary": "Salario no especificado",
                        "location": job_loc,
                        "modality": "Presencial",
                        "platform": "Indeed",
                        "description": f"Vacante de empleo de {title} en {company} vía Indeed.",
                        "killer_questions": []
                    })
                    if len(jobs) >= max_results:
                        break
    except Exception as e:
        print(f"[Indeed Scraper] HTTP Error: {e}")

    return jobs

async def search_indeed(keywords: str = "", location: str = "", max_results: int = 10, playwright: Any = None, headless: bool = True, skip_processed: bool = False) -> List[Dict[str, Any]]:
    """Primary entry point for searching Indeed with Playwright & HTTP fallback."""
    jobs = []
    if playwright:
        jobs = await search_indeed_playwright(keywords, location, max_results, playwright, skip_processed=skip_processed)
    if not jobs:
        jobs = await search_indeed_httpx(keywords, location, max_results, skip_processed=skip_processed)
    return jobs
