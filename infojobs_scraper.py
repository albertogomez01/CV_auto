import asyncio
import re
import urllib.parse
from typing import List, Dict, Any, Optional
import httpx
from bs4 import BeautifulSoup
from playwright.async_api import Playwright, Page, TimeoutError as PlaywrightTimeoutError
from browser import get_browser_context, create_stealth_page
from database import is_job_processed, record_application

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9"
}

def extract_job_id(url: str) -> str:
    """Extract unique job ID from InfoJobs URL."""
    match = re.search(r'of-i([a-zA-Z0-9]+)', url)
    if match:
        return f"of-i{match.group(1)}"
    return f"job_{abs(hash(url))}"

def parse_salary(salary_str: str) -> Optional[int]:
    """Parses numeric annual salary value from InfoJobs salary string."""
    if not salary_str or "no disponible" in salary_str.lower() or "no especificado" in salary_str.lower():
        return None
    clean_str = salary_str.replace(".", "").replace(",", ".")
    numbers = [int(n) for n in re.findall(r'\b\d{4,6}\b', clean_str)]
    if numbers:
        if "mes" in salary_str.lower() and max(numbers) < 10000:
            return max(numbers) * 12
        return max(numbers)
    return None

async def search_infojobs_http(keywords: str, location: str = "", max_results: int = 10, skip_processed: bool = False) -> List[Dict[str, Any]]:
    """Fast direct HTTP search on InfoJobs search list page."""
    jobs = []
    full_query = f"{keywords} {location}".strip() if (location and location.lower() not in keywords.lower()) else keywords.strip()
    encoded_kw = urllib.parse.quote(full_query)
    url = f"https://www.infojobs.net/jobsearch/search-results/list.xhtml?keyword={encoded_kw}"
    seen = set()

    try:
        async with httpx.AsyncClient(headers=DEFAULT_HEADERS, timeout=10.0, follow_redirects=True) as client:
            res = await client.get(url)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if "/of-" not in href and "of-i" not in href:
                        continue
                    if href.startswith("//"): href = "https:" + href
                    elif href.startswith("/"): href = "https://www.infojobs.net" + href

                    if href in seen: continue
                    seen.add(href)

                    title = a.get_text(strip=True)
                    if not title or len(title) < 3 or "Cookie" in title or "Aviso" in title:
                        continue

                    job_id = extract_job_id(href)
                    if skip_processed and is_job_processed(job_id):
                        continue

                    company = "Empresa en InfoJobs"
                    parent = a.find_parent(["li", "article", "div"])
                    if parent:
                        comp_el = parent.find(["a", "span", "p"], class_=lambda c: c and ("company" in c or "subtitle" in c))
                        if comp_el and comp_el.text.strip():
                            company = comp_el.text.strip()

                    jobs.append({
                        "id": job_id,
                        "title": title,
                        "company": company,
                        "link": href,
                        "salary": "Salario no disponible",
                        "location": location if location else "España",
                        "modality": "Presencial",
                        "platform": "InfoJobs",
                        "description": f"Oferta de empleo: {title} en {company}.",
                        "has_killer_questions": False,
                        "killer_questions": []
                    })
                    if len(jobs) >= max_results:
                        break
    except Exception as e:
        print(f"[InfoJobs Scraper] HTTP error: {e}")
    return jobs

async def search_jobs(
    playwright: Optional[Playwright] = None,
    keywords: str = "",
    location: str = "",
    salary_min: int = 0,
    modality: str = "Todas",
    allow_unspecified_salary: bool = True,
    max_results: int = 10,
    headless: bool = True,
    skip_processed: bool = False,
    **kwargs
) -> List[Dict[str, Any]]:
    """
    Searches for jobs on InfoJobs using ultra-fast list-page Playwright extraction with HTTP fallback.
    """
    jobs = []
    full_query = f"{keywords} {location}".strip() if (location and location.lower() not in keywords.lower()) else keywords.strip()
    encoded_kw = urllib.parse.quote(full_query)
    search_url = f"https://www.infojobs.net/jobsearch/search-results/list.xhtml?keyword={encoded_kw}"

    if playwright:
        try:
            context = await get_browser_context(playwright, headless=headless, use_storage_state=False)
            page = await create_stealth_page(context)
            await page.goto(search_url, wait_until="domcontentloaded", timeout=12000)
            await page.wait_for_timeout(1000)

            card_items = await page.evaluate("""
                () => {
                    const links = Array.from(document.querySelectorAll('a[href*="/of-"], a[href*="of-i"]'));
                    const results = [];
                    const seen = new Set();
                    
                    for (const a of links) {
                        let href = a.href;
                        if (!href.includes('/of-') && !href.includes('of-i')) continue;
                        if (seen.has(href)) continue;
                        seen.add(href);
                        
                        const text = a.innerText ? a.innerText.trim() : '';
                        if (!text || text.length < 3 || text.includes('Cookie') || text.includes('Aviso')) continue;
                        
                        let company = 'Empresa en InfoJobs';
                        let salary = 'Salario no disponible';
                        
                        let parent = a.closest('li, [class*="Offer"], [class*="card"], article, div');
                        if (parent) {
                            const compEl = parent.querySelector('[class*="company"], [class*="subtitle"], a[href*="/empresa/"]');
                            if (compEl && compEl.innerText.strip()) company = compEl.innerText.trim();
                            const salEl = parent.querySelector('[class*="salary"], [class*="salario"]');
                            if (salEl && salEl.innerText.strip()) salary = salEl.innerText.trim();
                        }
                        
                        results.push({ link: href, title: text, company, salary });
                    }
                    return results;
                }
            """)
            await context.close()

            for item in card_items[:max_results * 2]:
                link = item["link"]
                job_id = extract_job_id(link)
                if skip_processed and is_job_processed(job_id):
                    continue

                jobs.append({
                    "id": job_id,
                    "title": item["title"],
                    "company": item["company"],
                    "link": link,
                    "salary": item["salary"],
                    "location": location if location else "España",
                    "modality": modality if modality else "Presencial",
                    "platform": "InfoJobs",
                    "description": f"Vacante de empleo: {item['title']} en {item['company']}.",
                    "has_killer_questions": False,
                    "killer_questions": []
                })
                if len(jobs) >= max_results:
                    break
        except Exception as e:
            print(f"[InfoJobs Scraper] Playwright fast mode error: {e}")

    if not jobs:
        print("[InfoJobs Scraper] Playwright returned 0 jobs. Running fast HTTP fallback...")
        jobs = await search_infojobs_http(keywords, location, max_results)

    return jobs

async def apply_to_job(
    playwright: Playwright,
    job_url: str,
    killer_answers: Optional[List[Dict[str, str]]] = None,
    headless: bool = True
) -> Dict[str, Any]:
    """Applies to a job on InfoJobs."""
    context = await get_browser_context(playwright, headless=headless, use_storage_state=True)
    page = await create_stealth_page(context)
    try:
        await page.goto(job_url, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(1000)
        
        apply_btn = page.locator("button:has-text('Inscribirme'), a:has-text('Inscribirme')").first
        if await apply_btn.is_visible(timeout=3000):
            await apply_btn.click()
            await page.wait_for_timeout(2000)
            return {"status": "success", "message": "Postulación enviada en InfoJobs"}
        return {"status": "info", "message": "Botón de inscripción no encontrado directamente"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        await context.close()
