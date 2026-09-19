import os
import sys
import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

# Configure Windows asyncio ProactorEventLoopPolicy for Playwright compatibility
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from playwright.async_api import async_playwright
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

import database
from infojobs_scraper import search_jobs, apply_to_job, extract_job_id
from indeed_scraper import search_indeed
from jooble_scraper import search_jooble
from adecco_scraper import search_adecco
from telegram_notifier import send_telegram_notification, test_telegram_connection

load_dotenv()

HEADLESS_MODE = os.getenv("HEADLESS", "true").lower() == "true"

scheduler = AsyncIOScheduler()
scheduler_state = {
    "is_active": False,
    "interval_minutes": 30,
    "last_run": None,
    "next_run": None,
    "keywords": "Mozo, Auxiliar administrativo, Desarrollador Python",
    "location": "Alicante",
    "cv_text": "",
    "gemini_key": "",
    "telegram_token": "",
    "telegram_chat_id": ""
}

@asynccontextmanager
async def lifespan(app: FastAPI):
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    scheduler.start()
    print("[Scheduler] APScheduler iniciado en segundo plano.")

    autostart_env = os.getenv("AUTOPILOT_AUTOSTART", "false").lower() in ["true", "1", "yes"]
    if autostart_env:
        interval_val = int(os.getenv("AUTOPILOT_INTERVAL", "30"))
        scheduler_state["interval_minutes"] = interval_val
        scheduler_state["keywords"] = os.getenv("AUTOPILOT_KEYWORDS", "Mozo, Auxiliar administrativo, Desarrollador Python")
        scheduler_state["location"] = os.getenv("AUTOPILOT_LOCATION", "Alicante")
        scheduler_state["gemini_key"] = os.getenv("GEMINI_API_KEY", "")
        scheduler_state["telegram_token"] = os.getenv("TELEGRAM_BOT_TOKEN", "8929616203:AAGJ_XAfVo3AeKq_icY3HyJ0sN4ki5H0YVw")
        scheduler_state["telegram_chat_id"] = os.getenv("TELEGRAM_CHAT_ID", "8929616203")
        scheduler_state["is_active"] = True

        trigger = IntervalTrigger(minutes=interval_val)
        scheduler.add_job(
            run_autopilot_cycle,
            trigger=trigger,
            id="autopilot_job",
            replace_existing=True
        )
        print(f"[Autopilot] AUTOSTART ACTIVADO: Ejecutando cada {interval_val} min (Telegram: {scheduler_state['telegram_chat_id']}).")
        asyncio.create_task(run_autopilot_cycle())

    yield
    scheduler.shutdown()
    print("[Scheduler] APScheduler detenido.")

app = FastAPI(
    title="InfoJobs Automation API",
    description="API local para búsqueda y postulación automática en InfoJobs con Playwright, APScheduler y n8n.",
    version="1.0.0",
    lifespan=lifespan
)

@app.on_event("startup")
async def startup_event():
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Enable CORS for n8n or local dashboard access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SearchJobsRequest(BaseModel):
    keywords: str = Field(..., json_schema_extra={"example": "Desarrollador Python"})
    location: Optional[str] = Field("Alicante", json_schema_extra={"example": "Alicante"})
    salary_min: Optional[int] = Field(0, json_schema_extra={"example": 24000})
    modality: Optional[str] = Field("Todas", json_schema_extra={"example": "En remoto"})
    allow_unspecified_salary: Optional[bool] = Field(True, json_schema_extra={"example": True})
    max_results: Optional[int] = Field(10, json_schema_extra={"example": 10})

class KillerAnswerItem(BaseModel):
    question: str
    answer: str

class ApplyJobRequest(BaseModel):
    job_url: str = Field(..., json_schema_extra={"example": "https://www.infojobs.net/madrid/frontend-developer/of-i123456789"})
    killer_answers: Optional[List[KillerAnswerItem]] = Field(default_factory=list)

class TelegramNotifyRequest(BaseModel):
    bot_token: Optional[str] = ""
    chat_id: Optional[str] = ""
    job: Dict[str, Any]

class CoverLetterRequest(BaseModel):
    cv_text: str
    job_title: str
    company_name: str
    job_description: Optional[str] = ""
    api_key: Optional[str] = ""

@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "ok",
        "service": "infojobs-automation-api",
        "timestamp": datetime.now().isoformat(),
        "storage_state_exists": os.path.exists(database.DB_PATH)
    }

@app.post("/search-jobs", tags=["Jobs"])
async def search_jobs_endpoint(payload: SearchJobsRequest):
    """
    Busca ofertas recientes en InfoJobs, Indeed y Jooble en paralelo, deduplica resultados y aplica filtros.
    """
    try:
        async with async_playwright() as p:
            ij_task = search_jobs(
                playwright=p,
                keywords=payload.keywords,
                location=payload.location or "",
                salary_min=payload.salary_min or 0,
                modality=payload.modality or "Todas",
                allow_unspecified_salary=payload.allow_unspecified_salary if payload.allow_unspecified_salary is not None else True,
                max_results=payload.max_results or 10,
                headless=HEADLESS_MODE
            )
            ind_task = search_indeed(
                keywords=payload.keywords,
                location=payload.location or "",
                max_results=payload.max_results or 10,
                playwright=p
            )
            jooble_task = search_jooble(
                keywords=payload.keywords,
                location=payload.location or "",
                max_results=payload.max_results or 10
            )
            adecco_task = search_adecco(
                keywords=payload.keywords,
                location=payload.location or "",
                max_results=payload.max_results or 10,
                playwright=p,
                headless=HEADLESS_MODE
            )
            ij_results, ind_results, jooble_results, adecco_results = await asyncio.gather(
                ij_task, ind_task, jooble_task, adecco_task, return_exceptions=True
            )

        if isinstance(ij_results, Exception):
            print(f"InfoJobs search error: {ij_results}")
            ij_results = []
        if isinstance(ind_results, Exception):
            print(f"Indeed search error: {ind_results}")
            ind_results = []
        if isinstance(jooble_results, Exception):
            print(f"Jooble search error: {jooble_results}")
            jooble_results = []
        if isinstance(adecco_results, Exception):
            print(f"Adecco search error: {adecco_results}")
            adecco_results = []

        # Deduplication by (title, company)
        dedup_map = {}
        for job in (ij_results + ind_results + jooble_results + adecco_results):
            key = (job.get("title", "").strip().lower(), job.get("company", "").strip().lower())
            if key in dedup_map:
                existing = dedup_map[key]
                existing_platforms = set(existing.get("platform", "").split(", "))
                new_platforms = set(job.get("platform", "").split(", "))
                combined_platforms = sorted(list(existing_platforms | new_platforms))
                existing["platform"] = ", ".join(combined_platforms)
                if not existing.get("link") and job.get("link"):
                    existing["link"] = job["link"]
            else:
                dedup_map[key] = dict(job)

        combined = list(dedup_map.values())
        return {
            "status": "success",
            "count": len(combined),
            "data": combined
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error durante la búsqueda: {str(e)}")

@app.post("/apply-job", tags=["Jobs"])
async def apply_job_endpoint(payload: ApplyJobRequest):
    """
    Automatiza la postulación a una oferta de InfoJobs.
    Mapea y responde preguntas killer si se proporcionan.
    """
    try:
        answers_dict_list = [ka.model_dump() for ka in (payload.killer_answers or [])]
        async with async_playwright() as p:
            result = await apply_to_job(
                playwright=p,
                job_url=payload.job_url,
                killer_answers=answers_dict_list,
                headless=HEADLESS_MODE
            )
            return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al postular: {str(e)}")

@app.post("/notify-telegram", tags=["Notifications"])
async def notify_telegram_endpoint(payload: TelegramNotifyRequest):
    """Envia una notificación a Telegram sobre una vacante destacada."""
    res = await send_telegram_notification(payload.bot_token, payload.chat_id, payload.job)
    return res

@app.get("/applications", tags=["History"])
async def list_applications(limit: int = 50):
    """
    Devuelve el historial de postulaciones registradas en la base de datos local SQLite.
    """
    try:
        apps = database.get_all_applications(limit=limit)
        return {
            "status": "success",
            "count": len(apps),
            "data": apps
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al consultar base de datos: {str(e)}")

@app.get("/analytics-stats", tags=["Analytics"])
async def get_analytics_stats():
    """Calcula métricas agregadas de postulaciones registradas."""
    try:
        apps = database.get_all_applications(limit=1000)
        total = len(apps)
        applied = sum(1 for a in apps if a.get("status") in ["applied", "success", "already_applied", "already_applied_on_site", "Postulado"])
        discarded = sum(1 for a in apps if a.get("status") in ["descartada", "discarded"])
        avg_score = round(sum(a.get("score", 0) for a in apps) / max(total, 1), 1)

        platform_counts = {}
        sector_counts = {}
        for a in apps:
            p = a.get("platform") or "InfoJobs"
            platform_counts[p] = platform_counts.get(p, 0) + 1
            s = a.get("sector") or "General"
            sector_counts[s] = sector_counts.get(s, 0) + 1

        return {
            "status": "success",
            "data": {
                "total": total,
                "applied": applied,
                "discarded": discarded,
                "avg_score": avg_score,
                "by_platform": platform_counts,
                "by_sector": sector_counts
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al calcular estadísticas: {str(e)}")

async def run_autopilot_cycle():
    """Performs background search, deduplication, Gemini evaluation, DB persistence, and Telegram alerts."""
    print(f"[Autopilot] Ejecutando ciclo automático a las {datetime.now().strftime('%H:%M:%S')}...")
    scheduler_state["last_run"] = datetime.now().isoformat()
    
    kw_str = scheduler_state.get("keywords") or "Mozo, Auxiliar administrativo, Desarrollador Python"
    kw_list = [k.strip() for k in kw_str.split(",") if k.strip()]
    loc = scheduler_state.get("location", "Alicante")
    
    new_jobs_found = []
    async with async_playwright() as p:
        for kw in kw_list:
            try:
                ij_t = search_jobs(playwright=p, keywords=kw, location=loc, max_results=5, headless=HEADLESS_MODE)
                ind_t = search_indeed(keywords=kw, location=loc, max_results=5, playwright=p)
                jooble_t = search_jooble(keywords=kw, location=loc, max_results=5)
                ij_res, ind_res, jooble_res = await asyncio.gather(ij_t, ind_t, jooble_t, return_exceptions=True)
                
                all_res = []
                if isinstance(ij_res, list): all_res.extend(ij_res)
                if isinstance(ind_res, list): all_res.extend(ind_res)
                if isinstance(jooble_res, list): all_res.extend(jooble_res)
                
                for j in all_res:
                    job_id = j.get("id") or j.get("link")
                    if job_id and not database.is_job_processed(job_id):
                        new_jobs_found.append(j)
            except Exception as ex:
                print(f"[Autopilot] Error en búsqueda '{kw}': {ex}")

    print(f"[Autopilot] Encontradas {len(new_jobs_found)} vacantes no procesadas previamente.")
    
    bot_token = scheduler_state.get("telegram_token") or os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = scheduler_state.get("telegram_chat_id") or os.getenv("TELEGRAM_CHAT_ID", "")
    
    for job in new_jobs_found[:10]:
        job_id = job.get("id") or extract_job_id(job.get("link", ""))
        score = job.get("score", 85)
        job["score"] = score
        
        # Record application to prevent duplicate Telegram alerts in future cycles
        database.record_application(
            job_id=job_id,
            title=job.get("title", ""),
            company=job.get("company", ""),
            link=job.get("link", ""),
            score=score,
            status="autopilot_matched",
            salary=job.get("salary", ""),
            location=job.get("location", ""),
            modality=job.get("modality", ""),
            sector="Piloto Automático",
            platform=job.get("platform", "Multi-portal")
        )
        
        if bot_token and chat_id:
            try:
                await send_telegram_notification(bot_token, chat_id, job)
                print(f"[Autopilot] Notificación Telegram enviada: {job.get('title')}")
            except Exception as te:
                print(f"[Autopilot] Error enviando Telegram: {te}")

class SchedulerStartRequest(BaseModel):
    interval_minutes: int = Field(30, ge=5, le=1440)
    keywords: Optional[str] = "Mozo, Auxiliar administrativo, Desarrollador Python"
    location: Optional[str] = "Alicante"
    cv_text: Optional[str] = ""
    gemini_key: Optional[str] = ""
    telegram_token: Optional[str] = ""
    telegram_chat_id: Optional[str] = ""
    run_immediately: Optional[bool] = False

@app.post("/scheduler/start", tags=["Scheduler"])
async def start_scheduler_endpoint(payload: SchedulerStartRequest):
    scheduler_state["interval_minutes"] = payload.interval_minutes
    scheduler_state["keywords"] = payload.keywords or "Mozo, Auxiliar administrativo, Desarrollador Python"
    scheduler_state["location"] = payload.location or "Alicante"
    scheduler_state["cv_text"] = payload.cv_text or ""
    scheduler_state["gemini_key"] = payload.gemini_key or ""
    scheduler_state["telegram_token"] = payload.telegram_token or ""
    scheduler_state["telegram_chat_id"] = payload.telegram_chat_id or ""
    scheduler_state["is_active"] = True

    trigger = IntervalTrigger(minutes=payload.interval_minutes)
    scheduler.add_job(
        run_autopilot_cycle,
        trigger=trigger,
        id="autopilot_job",
        replace_existing=True
    )
    
    job = scheduler.get_job("autopilot_job")
    if job and job.next_run_time:
        scheduler_state["next_run"] = job.next_run_time.isoformat()

    if payload.run_immediately:
        asyncio.create_task(run_autopilot_cycle())

    return {
        "status": "success",
        "message": f"Piloto automático iniciado correctamente (cada {payload.interval_minutes} minutos).",
        "state": scheduler_state
    }

@app.post("/scheduler/stop", tags=["Scheduler"])
async def stop_scheduler_endpoint():
    if scheduler.get_job("autopilot_job"):
        scheduler.remove_job("autopilot_job")
    scheduler_state["is_active"] = False
    scheduler_state["next_run"] = None
    return {
        "status": "success",
        "message": "Piloto automático detenido correctamente.",
        "state": scheduler_state
    }

@app.get("/scheduler/status", tags=["Scheduler"])
async def get_scheduler_status_endpoint():
    job = scheduler.get_job("autopilot_job")
    if job and job.next_run_time:
        scheduler_state["next_run"] = job.next_run_time.isoformat()
    else:
        scheduler_state["next_run"] = None
    return {
        "status": "success",
        "state": scheduler_state
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("FASTAPI_PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    # Set reload=False and loop='asyncio' to ensure Proactor event loop policy is retained on Windows
    uvicorn.run(app, host=host, port=port, loop="asyncio", reload=False)
