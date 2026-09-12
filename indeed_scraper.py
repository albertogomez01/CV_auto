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

async def search_indeed_httpx(keywords: str, location: str = "", max_results: int = 10) -> List[Dict[str, Any]]:
    """Performs ultra-fast async HTTP scraping on Indeed Spain."""
    jobs = []
    q_param = urllib.parse.quote(keywords)
    l_param = urllib.parse.quote(location) if location else ""
    url = f"https://es.indeed.com/jobs?q={q_param}&l={l_param}"

    try:
        async with httpx.AsyncClient(headers=DEFAULT_HEADERS, timeout=12.0, follow_redirects=True) as client:
            res = await client.get(url)
            if res.status_code != 200 or "cloudflare" in res.text.lower() or "challenge" in res.text.lower():
                print("[Indeed Scraper] HTTP direct blocked or challenged, falling back to Playwright...")
                return []

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

                # Link extraction
                link = ""
                a_tag = card.select_one("a[href*='jk='], a.jcs-JobTitle, a[href*='/rc/clk']")
                if a_tag and a_tag.get("href"):
                    href = a_tag["href"]
                    if href.startswith("http"):
                        link = href
                    else:
                        link = f"https://es.indeed.com{href}"
                elif title_el.name == "a" and title_el.get("href"):
                    href = title_el["href"]
                    link = href if href.startswith("http") else f"https://es.indeed.com{href}"

                if not link:
                    continue

                job_id = extract_indeed_job_id(link)
                if is_job_processed(job_id):
                    continue

                modality = "Presencial"
                if "remoto" in title.lower() or "teletrabajo" in title.lower() or "remoto" in job_loc.lower():
                    modality = "En remoto"
                elif "híbrido" in title.lower() or "híbrido" in job_loc.lower():
                    modality = "Híbrido"

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

    return jobs

async def search_indeed_playwright(playwright, keywords: str, location: str = "", max_results: int = 10, headless: bool = True) -> List[Dict[str, Any]]:
    """Playwright fast DOM fallback for Indeed Spain if direct HTTP is challenged."""
    from browser import get_browser_context, create_stealth_page
    jobs = []
    try:
        context = await get_browser_context(playwright, headless=headless, use_storage_state=False)
        page = await create_stealth_page(context)
        
        q_param = urllib.parse.quote(keywords)
        l_param = urllib.parse.quote(location) if location else ""
        url = f"https://es.indeed.com/jobs?q={q_param}&l={l_param}"
        
        print(f"[Indeed Scraper] Navigating via Playwright: {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=18000)
        await page.wait_for_timeout(1500)

        card_items = await page.evaluate("""
            () => {
                const results = [];
                const cards = Array.from(document.querySelectorAll('div.job_seen_beacon, td.resultContent, div.cardOutline'));
                for (const c of cards) {
                    const titleEl = c.querySelector('h2.jobTitle, a.jcs-JobTitle, a[href*="jk="]');
                    if (!titleEl) continue;
                    const title = titleEl.innerText ? titleEl.innerText.trim() : '';
                    if (!title || title.length < 3) continue;

                    let href = titleEl.getAttribute('href') || '';
                    if (href && !href.startsWith('http')) {
                        href = 'https://es.indeed.com' + href;
                    }
                    if (!href) continue;

                    let company = 'Empresa en Indeed';
                    const compEl = c.querySelector('[data-testid="company-name"], .companyName');
                    if (compEl && compEl.innerText.trim()) company = compEl.innerText.trim();

                    let location = 'España';
                    const locEl = c.querySelector('[data-testid="text-location"], .companyLocation');
                    if (locEl && locEl.innerText.trim()) location = locEl.innerText.trim();

                    let salary = 'Salario no especificado';
                    const salEl = c.querySelector('[data-testid="attribute_snippet"], .salary-snippet-container');
                    if (salEl && salEl.innerText.trim()) salary = salEl.innerText.trim();

                    results.push({ link: href, title, company, location, salary });
                }
                return results;
            }
        """)

        for item in card_items[:max_results]:
            link = item["link"]
            job_id = extract_indeed_job_id(link)
            if is_job_processed(job_id):
                continue

            modality = "Presencial"
            if "remoto" in item["title"].lower() or "remoto" in item["location"].lower():
                modality = "En remoto"

            jobs.append({
                "id": job_id,
                "title": item["title"],
                "company": item["company"],
                "link": link,
                "salary": item["salary"],
                "location": item["location"],
                "modality": modality,
                "platform": "Indeed",
                "description": f"Vacante de empleo: {item['title']} en {item['company']}.",
                "killer_questions": []
            })
        await context.close()
    except Exception as e:
        print(f"[Indeed Scraper] Playwright fallback notice: {e}")

    return jobs

async def search_indeed(keywords: str = "", location: str = "", max_results: int = 10, playwright: Any = None, headless: bool = True) -> List[Dict[str, Any]]:
    """Primary entry point for searching Indeed with ultra-fast HTTP direct and Playwright fallback."""
    jobs = await search_indeed_httpx(keywords, location, max_results)
    if not jobs and playwright is not None and hasattr(playwright, "chromium"):
        jobs = await search_indeed_playwright(playwright, keywords, location, max_results, headless)
    return jobs
