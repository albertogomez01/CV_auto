import asyncio
import re
import urllib.parse
from typing import List, Dict, Any, Optional
from database import is_job_processed

def extract_adecco_id(url: str, raw_id: Optional[str] = None) -> str:
    if raw_id:
        return f"adecco_{raw_id}"
    match = re.search(r'([a-f0-9]{20,})', url, re.IGNORECASE)
    if match:
        return f"adecco_{match.group(1)}"
    return f"adecco_{abs(hash(url))}"

async def search_adecco(
    keywords: str = "",
    location: str = "",
    max_results: int = 10,
    playwright=None,
    headless: bool = True,
    **kwargs
) -> List[Dict[str, Any]]:
    """
    Busca ofertas de empleo en Adecco España (adecco.com/es-es/ofertas-trabajo).
    Soporta extracción mediante Playwright interceptando las respuestas JSON internas.
    """
    jobs: List[Dict[str, Any]] = []
    q_str = urllib.parse.quote(keywords)
    l_str = urllib.parse.quote(location) if location else ""
    search_url = f"https://www.adecco.com/es-es/ofertas-trabajo?k={q_str}&l={l_str}"

    print(f"[Adecco Scraper] Consultando vacantes en: {search_url}")

    close_playwright_instance = False
    p_instance = playwright

    try:
        if p_instance is None:
            from playwright.async_api import async_playwright
            playwright_ctx = await async_playwright().start()
            p_instance = playwright_ctx
            close_playwright_instance = True

        browser = await p_instance.chromium.launch(headless=headless)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        captured_jobs = []
        async def on_response(res):
            if "jobs/summarized" in res.url and res.status == 200:
                try:
                    data = await res.json()
                    if isinstance(data, dict) and "jobs" in data:
                        captured_jobs.extend(data["jobs"])
                except Exception:
                    pass

        page.on("response", on_response)

        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3.5)
        except Exception as ne:
            print(f"[Adecco Scraper] Aviso al navegar: {ne}")

        if captured_jobs:
            for item in captured_jobs[:max_results * 2]:
                raw_id = item.get("jobId", "")
                link_rel = item.get("jobDetailsUrl") or f"/es-es/ofertas-trabajo/{raw_id}"
                link = link_rel if link_rel.startswith("http") else f"https://www.adecco.com{link_rel}"

                job_id = extract_adecco_id(link, raw_id)
                title = item.get("jobTitle") or "Vacante en Adecco"
                company = item.get("brandName") or "Adecco España"
                city = item.get("city") or location or "España"

                if is_job_processed(job_id=job_id, link=link, title=title, company=company):
                    continue

                salary = item.get("salaryRange") or item.get("contractTypeTitle") or "Según convenio / No especificado"
                modality = "En remoto" if ("remoto" in title.lower() or "teletrabajo" in title.lower()) else "Presencial"

                jobs.append({
                    "id": job_id,
                    "title": title,
                    "company": company,
                    "link": link,
                    "salary": salary,
                    "location": city,
                    "modality": modality,
                    "platform": "Adecco",
                    "description": f"Vacante de empleo en Adecco: {title} en {city}.",
                    "killer_questions": []
                })

                if len(jobs) >= max_results:
                    break
        else:
            # DOM fallback
            links = await page.eval_on_selector_all("a", "els => els.map(e => ({href: e.href, text: e.innerText.trim()}))")
            seen = set()
            for l in links:
                href = l["href"]
                text = l["text"]
                if "/ofertas-trabajo/" in href and len(href.split("/")) > 5 and href not in seen:
                    seen.add(href)
                    title = text if (text and len(text) > 4 and "VER MÁS" not in text) else "Oferta de Empleo Adecco"
                    j_id = extract_adecco_id(href)
                    if is_job_processed(job_id=j_id, link=href, title=title, company="Adecco España"):
                        continue
                    jobs.append({
                        "id": j_id,
                        "title": title,
                        "company": "Adecco España",
                        "link": href,
                        "salary": "Según convenio",
                        "location": location or "España",
                        "modality": "Presencial",
                        "platform": "Adecco",
                        "description": f"Vacante de empleo Adecco: {title}.",
                        "killer_questions": []
                    })
                    if len(jobs) >= max_results:
                        break

        await browser.close()
        if close_playwright_instance and p_instance:
            await p_instance.stop()

    except Exception as e:
        print(f"[Adecco Scraper] Error durante la búsqueda: {e}")

    print(f"[Adecco Scraper] Éxito: {len(jobs)} vacantes obtenidas de Adecco.")
    return jobs
