import asyncio
import re
import urllib.parse
from typing import List, Dict, Any, Optional
import httpx
from bs4 import BeautifulSoup
from playwright.async_api import Playwright, Page, TimeoutError as PlaywrightTimeoutError
from browser import get_browser_context, create_stealth_page
from database import is_job_processed, record_application

async def dismiss_cookies(page: Page):
    """Auxiliary helper to accept/dismiss common cookie banners."""
    cookie_selectors = [
        "#didomi-notice-agree-button",
        "button:has-text('Aceptar y continuar')",
        "button:has-text('Aceptar todas')",
        "button:has-text('Aceptar')",
        "button[id*='cookie']",
        "button[class*='cookie']"
    ]
    for selector in cookie_selectors:
        try:
            btn = page.locator(selector).first
            if await btn.is_visible(timeout=1500):
                await btn.click()
                await page.wait_for_timeout(1000)
                break
        except Exception:
            pass

def extract_job_id(url: str) -> str:
    """Extract unique job ID from InfoJobs URL."""
    match = re.search(r'of-i([a-zA-Z0-9]+)', url)
    if match:
        return f"of-i{match.group(1)}"
    # Fallback to hash of URL if pattern fails
    return f"job_{abs(hash(url))}"

def parse_salary(salary_str: str) -> Optional[int]:
    """Parses numeric annual salary value from InfoJobs salary string."""
    if not salary_str or "no disponible" in salary_str.lower() or "no especificado" in salary_str.lower():
        return None
    clean_str = salary_str.replace(".", "").replace(",", ".")
    numbers = [int(n) for n in re.findall(r'\b\d{4,6}\b', clean_str)]
    if numbers:
        # If monthly salary (e.g. 1500 €/mes)
        if "mes" in salary_str.lower() and max(numbers) < 10000:
            return max(numbers) * 12
        return max(numbers)
    return None

async def search_infojobs_rss(keywords: str, location: str = "", max_results: int = 10) -> List[Dict[str, Any]]:
    """Fetches InfoJobs jobs via RSS XML feed (immune to Cloudflare JS challenges)."""
    jobs = []
    full_query = f"{keywords} {location}".strip() if (location and location.lower() not in keywords.lower()) else keywords.strip()
    encoded_kw = urllib.parse.quote(full_query)
    rss_url = f"https://www.infojobs.net/jobsearch/search-results/rss.xhtml?keyword={encoded_kw}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/xml,application/xml,application/xhtml+xml,text/html;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8"
    }
    try:
        async with httpx.AsyncClient(headers=headers, timeout=12.0, follow_redirects=True) as client:
            res = await client.get(rss_url)
            if res.status_code == 200 and ("<item>" in res.text or "<rss" in res.text):
                soup = BeautifulSoup(res.text, "xml" if "xml" in res.headers.get("content-type", "") else "html.parser")
                items = soup.find_all("item")
                for item in items[:max_results * 2]:
                    t_el = item.find("title")
                    l_el = item.find("link")
                    d_el = item.find("description")
                    c_el = item.find("author") or item.find("dc:creator")
                    
                    if not t_el or not l_el:
                        continue
                    
                    title = t_el.get_text(strip=True)
                    link = l_el.get_text(strip=True)
                    company = c_el.get_text(strip=True) if c_el else "Empresa en InfoJobs"
                    job_id = extract_job_id(link)
                    if is_job_processed(job_id):
                        continue
                        
                    jobs.append({
                        "id": job_id,
                        "title": title,
                        "company": company,
                        "link": link,
                        "salary": "Salario publicado en oferta",
                        "location": location if location else "España",
                        "modality": "Presencial",
                        "platform": "InfoJobs",
                        "description": d_el.get_text(strip=True) if d_el else f"Oferta de empleo: {title} en {company}.",
                        "has_killer_questions": False,
                        "killer_questions": []
                    })
                    if len(jobs) >= max_results:
                        break
    except Exception as e:
        print(f"[InfoJobs Scraper] RSS Error: {e}")
    return jobs

async def search_jobs(
    playwright: Playwright,
    keywords: str,
    location: str = "",
    salary_min: int = 0,
    modality: str = "Todas",
    allow_unspecified_salary: bool = True,
    max_results: int = 10,
    headless: bool = True,
    **kwargs
) -> List[Dict[str, Any]]:
    """
    Searches for jobs on InfoJobs using clean browser context for maximum speed and reliability.
    """
    context = await get_browser_context(playwright, headless=headless, use_storage_state=False)
    page = await create_stealth_page(context)
    jobs = []

    try:
        full_query = f"{keywords} {location}".strip() if (location and location.lower() not in keywords.lower()) else keywords.strip()
        encoded_kw = urllib.parse.quote(full_query)
        search_url = f"https://www.infojobs.net/jobsearch/search-results/list.xhtml?keyword={encoded_kw}"
        if salary_min > 0:
            search_url += f"&salaryMin={salary_min}"
        if modality and modality.lower() != "todas":
            if "remoto" in modality.lower() or "teletrabajo" in modality.lower():
                search_url += "&teleworking=teletrabajo-100"
            elif "híbrido" in modality.lower() or "hibrido" in modality.lower():
                search_url += "&teleworking=hibrido"

        print(f"[Scraper] Navigating to search URL: {search_url}")
        await page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
        await dismiss_cookies(page)
        await page.wait_for_timeout(1500)

        # Fast DOM extraction via page.evaluate
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
                        if (compEl && compEl.innerText.trim()) company = compEl.innerText.trim();
                        const salEl = parent.querySelector('[class*="salary"], [class*="salario"]');
                        if (salEl && salEl.innerText.trim()) salary = salEl.innerText.trim();
                    }
                    
                    results.push({ link: href, title: text, company, salary });
                }
                return results;
            }
        """)

        print(f"[Scraper] Found {len(card_items)} offer items on search list page.")

        for item in card_items[:max_results]:
            link = item["link"]
            job_id = extract_job_id(link)

            # Deduplication check in SQLite database
            if is_job_processed(job_id):
                print(f"[Scraper] Skipping already processed job_id: {job_id}")
                continue
                print(f"[Scraper] Skipping already processed job_id: {job_id}")
                continue

            title = item["title"]
            company = item["company"]
            salary = item["salary"]
            job_location = location if location else "España"
            job_modality = modality if modality else "Presencial"
            description = f"Vacante de empleo: {title} en {company}."
            killer_questions = []

            try:
                # Detail page extraction
                detail_page = await create_stealth_page(context)
                await detail_page.goto(link, wait_until="domcontentloaded", timeout=25000)
                await dismiss_cookies(detail_page)
                await detail_page.wait_for_timeout(1000)

                page_title = await detail_page.title()
                
                # Check if detail page loaded real offer content
                if not ("humano o un robot" in page_title.lower() or "cloudflare" in page_title.lower()):
                    t_el = detail_page.locator("h1, .ij-OfferDetail-title, [data-test='offer-title']").first
                    if await t_el.count() > 0:
                        dt_title = (await t_el.text_content()).strip()
                        if dt_title and "humano" not in dt_title.lower():
                            title = dt_title

                    c_el = detail_page.locator(".ij-OfferDetail-header-company-name, a[href*='/empresa/'], [data-test='company-name']").first
                    if await c_el.count() > 0:
                        dt_comp = (await c_el.text_content()).strip()
                        if dt_comp:
                            company = dt_comp

                    s_el = detail_page.locator(".ij-OfferDetail-salary, [data-test='salary'], [class*='salary']").first
                    if await s_el.count() > 0:
                        dt_sal = (await s_el.text_content()).strip()
                        if dt_sal:
                            salary = dt_sal

                    l_el = detail_page.locator(".ij-OfferDetail-location, [data-test='location'], [class*='location']").first
                    if await l_el.count() > 0:
                        dt_loc = (await l_el.text_content()).strip()
                        if dt_loc:
                            job_location = dt_loc

                    d_el = detail_page.locator(".ij-OfferDetail-description, [id*='description'], main").first
                    if await d_el.count() > 0:
                        dt_desc = (await d_el.text_content()).strip()
                        if dt_desc and len(dt_desc) > 20:
                            description = dt_desc

                    q_elements = await detail_page.locator(".ij-OfferDetail-questions li, [class*='question']").all()
                    for q_el in q_elements:
                        q_text = (await q_el.text_content()).strip()
                        if q_text and len(q_text) > 3:
                            killer_questions.append(q_text)

                await detail_page.close()
                await asyncio.sleep(1)

            except Exception as e:
                print(f"[Scraper] Warning parsing detail for {link}: {e}. Using list page card data.")

            # Filter out by minimum salary threshold if required
            numeric_salary = parse_salary(salary)
            if salary_min > 0:
                if numeric_salary is not None and numeric_salary < salary_min:
                    print(f"[Scraper] Discarding job '{title}' - salary {numeric_salary} € below min {salary_min} €")
                    continue
                if numeric_salary is None and not allow_unspecified_salary:
                    print(f"[Scraper] Discarding job '{title}' - salary unspecified and allow_unspecified_salary is False")
                    continue

            jobs.append({
                "id": job_id,
                "title": title,
                "company": company,
                "link": link,
                "salary": salary,
                "location": job_location,
                "modality": job_modality,
                "platform": "InfoJobs",
                "description": description[:3000],
                "has_killer_questions": len(killer_questions) > 0,
                "killer_questions": killer_questions
            })

    finally:
        await context.close()

    if not jobs:
        print("[InfoJobs Scraper] Playwright DOM returned 0 jobs (Cloudflare or block). Attempting InfoJobs RSS XML feed fallback...")
        jobs = await search_infojobs_rss(keywords, location, max_results)

    return jobs

async def apply_to_job(
    playwright: Playwright,
    job_url: str,
    killer_answers: Optional[List[Dict[str, str]]] = None,
    headless: bool = True
) -> Dict[str, Any]:
    """
    Automates the application to an InfoJobs job URL.
    Fills in killer questions if provided and confirms application.
    """
    job_id = extract_job_id(job_url)
    
    if is_job_processed(job_id):
        return {
            "status": "already_applied",
            "job_id": job_id,
            "message": "Esta oferta ya fue procesada anteriormente en la base de datos."
        }

    context = await get_browser_context(playwright, headless=headless)
    page = await create_stealth_page(context)
    
    title = "Oferta InfoJobs"
    company = "Empresa"

    try:
        print(f"[Apply] Navigating to job page: {job_url}")
        await page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
        await dismiss_cookies(page)

        # Try to extract title & company for DB logging
        try:
            t_el = page.locator("h1").first
            if await t_el.count() > 0:
                title = (await t_el.text_content()).strip()
        except Exception:
            pass

        # Look for application button
        apply_btn_selectors = [
            "button:has-text('Inscribirme en esta oferta')",
            "a:has-text('Inscribirme en esta oferta')",
            "button:has-text('Inscribirme')",
            "a:has-text('Inscribirme')",
            "[data-test='apply-button']",
            ".ij-Button--primary:has-text('Inscribirme')"
        ]

        apply_btn = None
        for sel in apply_btn_selectors:
            loc = page.locator(sel).first
            if await loc.count() > 0 and await loc.is_visible():
                apply_btn = loc
                break

        if not apply_btn:
            # Check if user is already registered on page
            already_applied_loc = page.locator("text='Ya estás inscrito'").first
            if await already_applied_loc.count() > 0:
                record_application(job_id, title, company, job_url, score=0, status="already_applied_on_site")
                return {
                    "status": "already_applied",
                    "job_id": job_id,
                    "message": "Ya apareces inscrito en la plataforma InfoJobs."
                }
            
            return {
                "status": "error",
                "job_id": job_id,
                "message": "No se encontró el botón de inscripción o requiere inicio de sesión."
            }

        # Click application button
        print("[Apply] Clicking apply button...")
        await apply_btn.click()
        await page.wait_for_timeout(2000)

        # Handle Killer Questions / Questionnaire if present
        answers_map = {ka.get("question", "").lower().strip(): ka.get("answer", "") for ka in (killer_answers or [])}
        
        # Check for inputs / questions on modal or page
        question_inputs = await page.locator("textarea, input[type='text'], input[type='number']").all()
        for inp in question_inputs:
            if await inp.is_visible():
                # Attempt to get question label
                parent_text = ""
                try:
                    parent = inp.locator("xpath=ancestor::div[contains(@class,'question') or contains(@class,'field') or contains(@class,'form')]").first
                    if await parent.count() > 0:
                        parent_text = (await parent.text_content()).lower().strip()
                except Exception:
                    pass

                # Find best matching answer
                matched_answer = None
                for q_key, ans_val in answers_map.items():
                    if q_key in parent_text or any(w in parent_text for w in q_key.split() if len(w) > 3):
                        matched_answer = ans_val
                        break

                if not matched_answer and answers_map:
                    # Fallback to first available answer
                    matched_answer = list(answers_map.values())[0]

                if matched_answer:
                    print(f"[Apply] Filling question input with answer: {matched_answer}")
                    await inp.fill(str(matched_answer))

        # Check for radio buttons / options
        radio_groups = await page.locator("input[type='radio']").all()
        if radio_groups:
            # Click first radio option per group if not selected
            for radio in radio_groups:
                try:
                    if await radio.is_visible() and not await radio.is_checked():
                        await radio.check(force=True)
                except Exception:
                    pass

        # Look for confirm / continue button
        confirm_btn_selectors = [
            "button:has-text('Confirmar inscripción')",
            "button:has-text('Continuar')",
            "button:has-text('Guardar y continuar')",
            "button:has-text('Enviar')",
            "button[type='submit']"
        ]

        for c_sel in confirm_btn_selectors:
            c_btn = page.locator(c_sel).first
            if await c_btn.count() > 0 and await c_btn.is_visible():
                print(f"[Apply] Clicking confirm button: {c_sel}")
                await c_btn.click()
                await page.wait_for_timeout(3000)
                break

        # Final verification check
        success_indicators = [
            "Te has inscrito",
            "Inscripción completada",
            "Ya estás inscrito",
            "Gracias por inscribirte"
        ]

        page_content = await page.content()
        is_success = any(ind in page_content for ind in success_indicators)

        status_result = "success" if is_success else "submitted"
        
        # Record in database
        record_application(
            job_id=job_id,
            title=title,
            company=company,
            link=job_url,
            score=100,
            status=status_result,
            killer_answers=killer_answers
        )

        return {
            "status": "success",
            "job_id": job_id,
            "message": "Postulación completada con éxito."
        }

    except Exception as e:
        print(f"[Apply] Error during application: {e}")
        return {
            "status": "error",
            "job_id": job_id,
            "message": f"Error al procesar la postulación: {str(e)}"
        }

    finally:
        await context.close()
