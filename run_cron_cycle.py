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
from agent_runner import evaluate_job_with_gemini, get_gemini_client

async def run_user_cycle(user: Dict[str, Any], token: str, gemini_client: Any) -> int:
    chat_id = str(user["chat_id"])
    username = user.get("username", "Usuario")
    keywords = user.get("job_title") or "Desarrollador Python"
    location = user.get("location") or "Alicante"
    cv_text = user.get("cv_text") or f"Perfil profesional enfocado en {keywords}."
    max_results = 10
    min_score = 50

    print("\n" + "=" * 70)
    print(f"👤 PROCESANDO USUARIO: @{username} (Chat ID: {chat_id})")
    print(f"📌 Búsqueda: '{keywords}' | Ubicación: '{location}' | MinScore: {min_score}%")
    print("=" * 70)

    # 1. Scrapers en paralelo para este usuario
    all_jobs: List[Dict[str, Any]] = []

    # InfoJobs
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
        print(f"⚠️ [Cron User {chat_id}] Error InfoJobs: {e}")

    # Indeed
    try:
        ind_jobs = await search_indeed_httpx(keywords=keywords, location=location, max_results=max_results)
        for j in ind_jobs:
            j["platform"] = "Indeed"
        all_jobs.extend(ind_jobs)
    except Exception as e:
        print(f"⚠️ [Cron User {chat_id}] Error Indeed: {e}")

    # Jooble
    try:
        joo_jobs = await search_jooble(keywords=keywords, location=location, max_results=max_results)
        for j in joo_jobs:
            j["platform"] = "Jooble"
        all_jobs.extend(joo_jobs)
    except Exception as e:
        print(f"⚠️ [Cron User {chat_id}] Error Jooble: {e}")

    # Adecco
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
        print(f"⚠️ [Cron User {chat_id}] Error Adecco: {e}")

    print(f"🔍 Vacantes obtenidas para @{username}: {len(all_jobs)}")

    # 2. Deduplicar por usuario y verificar SQLite
    dedup_map = {}
    for job in all_jobs:
        title = job.get("title", "").strip()
        company = job.get("company", "").strip()
        link = job.get("link", "")
        job_id = job.get("id") or job.get("job_id") or link

        if not title or not company or not link:
            continue

        if database.is_job_processed(job_id=job_id, link=link, title=title, company=company, user_id=chat_id):
            continue

        key = (title.lower(), company.lower())
        if key not in dedup_map:
            dedup_map[key] = job

    unprocessed_jobs = list(dedup_map.values())
    print(f"✅ Nuevas vacantes sin procesar para @{username}: {len(unprocessed_jobs)}")

    if not unprocessed_jobs:
        print(f"ℹ️ Sin nuevas ofertas para @{username} en este ciclo.")
        return 0

    # 3. Evaluar con Gemini / Heurística usando el CV del usuario
    notified_count = 0
    for idx, job in enumerate(unprocessed_jobs, start=1):
        title = job.get("title", "")
        company = job.get("company", "")
        link = job.get("link", "")
        job_id = job.get("id") or job.get("job_id") or link

        print(f"\n📄 [{idx}/{len(unprocessed_jobs)}] Evaluando vacante: '{title}' ({company}) - {job.get('platform')}")

        eval_res = evaluate_job_with_gemini(
            client_info=gemini_client if gemini_client else ("none", ""),
            model_name="gemini-1.5-flash",
            cv_instructions=cv_text,
            job=job
        )

        score = eval_res.get("score", 70)
        reasoning = eval_res.get("reasoning", "")
        job["score"] = score
        job["reasoning"] = reasoning

        print(f"📊 Coincidencia: {score}% | {reasoning}")

        if score >= min_score:
            print(f"🎯 Score >= {min_score}% -> Notificando al chat ID {chat_id}...")
            
            # Registrar en SQLite vinculado al chat_id del usuario
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
                platform=job.get("platform"),
                user_id=chat_id
            )

            # Enviar notificación directa por Telegram a este usuario
            if token and chat_id:
                notify_res = await send_telegram_notification(token, chat_id, job)
                print(f"🔔 Telegram: {notify_res.get('message')}")
                notified_count += 1
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
                platform=job.get("platform"),
                user_id=chat_id
            )

    return notified_count

async def run_single_cycle():
    print("=" * 70)
    print("🤖 INICIANDO CICLO CRON MULTIUSUARIO DESATENDIDO")
    print("=" * 70)

    # 1. Inicializar base de datos SQLite
    database.init_db()

    # 2. Consultar todos los usuarios activos
    active_users = database.get_active_users()

    # Si no hay usuarios en la base de datos pero existen credenciales por entorno, crear usuario por defecto
    if not active_users:
        env_chat = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        if env_chat:
            print(f"ℹ️ Creando perfil inicial para el Chat ID del entorno: {env_chat}")
            default_user = database.upsert_user(
                chat_id=env_chat,
                username="Admin",
                job_title="Mozo, Auxiliar administrativo, Desarrollador Python",
                location="Alicante",
                cv_text="",
                active=1
            )
            active_users = [default_user]

    if not active_users:
        print("ℹ️ No hay usuarios activos registrados en la base de datos. Finalizando ciclo limpiamente.")
        print("=" * 70)
        return

    print(f"📋 Usuarios activos encontrados para escanear: {len(active_users)}")

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    gemini_client = get_gemini_client(api_key) if api_key else None

    total_notified = 0
    for u in active_users:
        try:
            cnt = await run_user_cycle(user=u, token=token, gemini_client=gemini_client)
            total_notified += cnt
        except Exception as ue:
            print(f"❌ Error procesando ciclo para el usuario {u.get('chat_id')}: {ue}")

    print("\n" + "=" * 70)
    print(f"🎉 CICLO CRON MULTIUSUARIO FINALIZADO: {total_notified} vacantes notificadas a {len(active_users)} usuario(s).")
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
