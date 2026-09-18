import os
import sys
import json
import asyncio
import re
from typing import Dict, Any, List
from dotenv import load_dotenv

load_dotenv()

# Configure Proactor event loop on Windows if running locally
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import database
from infojobs_scraper import search_jobs as search_infojobs
from indeed_scraper import search_indeed_httpx
from jooble_scraper import search_jooble
from adecco_scraper import search_adecco
from telegram_notifier import send_telegram_notification
from agent_runner import evaluate_job_with_gemini, get_gemini_client, load_agent_config

CONFIG_FILE = "bot_config.json"
CV_FILE = "user_cv.txt"

DEFAULT_CONFIG = {
    "keywords": "Mozo, Auxiliar administrativo, Desarrollador Python",
    "location": "Alicante",
    "max_results": 10,
    "min_score": 50
}

def load_config() -> Dict[str, Any]:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        except Exception as e:
            print(f"[Cron] Error leyendo config: {e}")
    return DEFAULT_CONFIG.copy()

def load_cv_text() -> str:
    if os.path.exists(CV_FILE):
        try:
            with open(CV_FILE, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    return ""

async def run_single_cycle():
    print("=" * 70)
    print("🤖 INICIANDO CICLO CRON DESATENDIDO DE BÚSQUEDA Y EVALUACIÓN DE EMPLEO")
    print("=" * 70)

    # 1. Inicializar base de datos SQLite
    database.init_db()

    config = load_config()
    keywords = config.get("keywords", "Mozo, Auxiliar administrativo, Desarrollador Python")
    location = config.get("location", "Alicante")
    max_results = int(config.get("max_results", 10))
    min_score = int(config.get("min_score", 50))
    cv_text = load_cv_text()

    print(f"📌 Parámetros de búsqueda: Búsqueda='{keywords}' | Ubicación='{location}' | Máx={max_results} | MinScore={min_score}%")

    # 2. Ejecutar scrapers en paralelo
    all_jobs: List[Dict[str, Any]] = []

    # Scraping InfoJobs (Playwright)
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            ij_jobs = await search_infojobs(
                playwright=p,
                keywords=keywords,
                location=location,
                max_results=max_results,
                headless=True
            )
            for j in ij_jobs:
                j["platform"] = "InfoJobs"
            all_jobs.extend(ij_jobs)
    except Exception as e:
        print(f"⚠️ [Cron] Error scraping InfoJobs: {e}")

    # Scraping Indeed (HTTP)
    try:
        ind_jobs = await search_indeed_httpx(keywords=keywords, location=location, max_results=max_results)
        for j in ind_jobs:
            j["platform"] = "Indeed"
        all_jobs.extend(ind_jobs)
    except Exception as e:
        print(f"⚠️ [Cron] Error scraping Indeed: {e}")

    # Scraping Jooble (HTTP)
    try:
        joo_jobs = await search_jooble(keywords=keywords, location=location, max_results=max_results)
        for j in joo_jobs:
            j["platform"] = "Jooble"
        all_jobs.extend(joo_jobs)
    except Exception as e:
        print(f"⚠️ [Cron] Error scraping Jooble: {e}")

    # Scraping Adecco (Playwright)
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            adecco_jobs = await search_adecco(
                keywords=keywords,
                location=location,
                max_results=max_results,
                playwright=p,
                headless=True
            )
            for j in adecco_jobs:
                j["platform"] = "Adecco"
            all_jobs.extend(adecco_jobs)
    except Exception as e:
        print(f"⚠️ [Cron] Error scraping Adecco: {e}")

    print(f"\n🔍 Vacantes brutas consolidadas: {len(all_jobs)}")

    # 3. Deduplicación por (título, empresa) y verificación contra SQLite
    dedup_map = {}
    for job in all_jobs:
        title = job.get("title", "").strip()
        company = job.get("company", "").strip()
        link = job.get("link", "")
        job_id = job.get("id") or job.get("job_id") or link

        if not title or not company or not link:
            continue

        if database.is_job_processed(job_id=job_id, link=link, title=title, company=company):
            continue

        key = (title.lower(), company.lower())
        if key not in dedup_map:
            dedup_map[key] = job

    unprocessed_jobs = list(dedup_map.values())
    print(f"✅ Nuevas vacantes únicas a evaluar: {len(unprocessed_jobs)}")

    if not unprocessed_jobs:
        print("ℹ️ No hay nuevas vacantes para evaluar en este ciclo.")
        print("=" * 70)
        return

    # 4. Evaluación de vacantes con Gemini / Heurística
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    gemini_client = get_gemini_client(api_key) if api_key else None
    
    agent_instructions = cv_text if cv_text else "Perfil general con experiencia laboral adaptable."

    notified_count = 0
    for idx, job in enumerate(unprocessed_jobs, start=1):
        title = job.get("title", "")
        company = job.get("company", "")
        link = job.get("link", "")
        job_id = job.get("id") or job.get("job_id") or link

        print(f"\n------------------------------------------------------------")
        print(f"📄 [{idx}/{len(unprocessed_jobs)}] Evaluando: '{title}' ({company}) - {job.get('platform')}")

        eval_res = evaluate_job_with_gemini(
            client_info=gemini_client if gemini_client else ("none", ""),
            model_name="gemini-1.5-flash",
            cv_instructions=agent_instructions,
            job=job
        )

        score = eval_res.get("score", 70)
        reasoning = eval_res.get("reasoning", "")
        job["score"] = score
        job["reasoning"] = reasoning

        print(f"📊 Coincidencia: {score}% | {reasoning}")

        if score >= min_score:
            print(f"🎯 Score >= {min_score}% -> Registrando y enviando notificación Telegram...")
            
            # Registrar en SQLite
            database.record_application(
                job_id=job_id,
                title=title,
                company=company,
                link=link,
                score=score,
                status="evaluada",
                salary=job.get("salary"),
                location=job.get("location"),
                modality=job.get("modality"),
                platform=job.get("platform")
            )

            # Notificar vía Telegram
            token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
            chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
            if token and chat_id:
                notify_res = await send_telegram_notification(token, chat_id, job)
                print(f"🔔 Telegram: {notify_res.get('message')}")
                notified_count += 1
            else:
                print("⚠️ Notificación Telegram omitida (faltan credenciales TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID).")
        else:
            print(f"⏭️ Score inferior a {min_score}%. Se descarta.")
            database.discard_job(
                job_id=job_id,
                title=title,
                company=company,
                link=link,
                score=score,
                salary=job.get("salary"),
                location=job.get("location"),
                modality=job.get("modality"),
                platform=job.get("platform")
            )

    print("\n" + "=" * 70)
    print(f"🎉 CICLO CRON FINALIZADO: {notified_count} vacantes notificadas de {len(unprocessed_jobs)} evaluadas.")
    print("=" * 70)

def main():
    try:
        asyncio.run(run_single_cycle())
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error en la ejecución del ciclo cron: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
