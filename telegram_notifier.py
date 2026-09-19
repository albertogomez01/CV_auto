import os
import asyncio
import hashlib
from typing import Dict, Any, Optional
import httpx
from dotenv import load_dotenv

load_dotenv()


async def send_telegram_notification(
    bot_token: str,
    chat_id: str,
    job: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Dispatches a clean HTML notification to a Telegram Chat with inline action buttons [✅ Postular] & [❌ Descartar].
    """
    token = bot_token.strip() if bot_token else os.getenv("TELEGRAM_BOT_TOKEN", "8929616203:AAGJ_XAfVo3AeKq_icY3HyJ0sN4ki5H0YVw").strip()
    cid = chat_id.strip() if chat_id else os.getenv("TELEGRAM_CHAT_ID", "8929616203").strip()

    if not token or not cid:
        return {"status": "skipped", "message": "Telegram Bot Token or Chat ID not configured."}

    title = job.get("title", "Oferta de Empleo")
    company = job.get("company", "Empresa")
    score = job.get("score", 85)
    platform = job.get("platform", "InfoJobs")
    sector = job.get("sector", "General")
    link = job.get("link", "https://www.infojobs.net/")
    salary = job.get("salary", "Salario según convenio")
    location = job.get("location", "España")

    job_id = job.get("job_id") or job.get("id") or link or f"{title}_{company}"
    job_hash = hashlib.md5(str(job_id).encode("utf-8")).hexdigest()[:16]

    msg_text = (
        f"🚨 <b>¡NUEVA VACANTE DESTACADA ({score}% Coincidencia)!</b>\n\n"
        f"📌 <b>Puesto:</b> {title}\n"
        f"🏢 <b>Empresa:</b> {company}\n"
        f"📍 <b>Ubicación:</b> {location}\n"
        f"💰 <b>Salario:</b> {salary}\n"
        f"🏷️ <b>Plataforma:</b> {platform}\n"
        f"📦 <b>Sector:</b> {sector}\n\n"
        f"<i>¿Qué deseas hacer con esta vacante? Selecciona una opción abajo:</i>"
    )

    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "✅ Postular", "callback_data": f"apply_{job_hash}"},
                {"text": "❌ Descartar", "callback_data": f"dismiss_{job_hash}"}
            ],
            [{"text": "🔗 Ver Oferta en la Web", "url": link}]
        ]
    }

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": cid,
        "text": msg_text,
        "parse_mode": "HTML",
        "reply_markup": reply_markup,
        "disable_web_page_preview": False
    }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            res = await client.post(url, json=payload)
            res_data = res.json()
            if res.status_code == 200 and res_data.get("ok"):
                return {"status": "success", "message": "Notificación enviada a Telegram con éxito."}
            else:
                err_desc = res_data.get("description", "Error desconocido en Telegram API")
                return {"status": "error", "message": f"Error de Telegram API: {err_desc}"}
    except Exception as e:
        return {"status": "error", "message": f"Error de red enviando a Telegram: {str(e)}"}

async def test_telegram_connection(bot_token: str, chat_id: str) -> Dict[str, Any]:
    """Test connection with specified Telegram Bot credentials."""
    sample_job = {
        "title": "Desarrollador / Especialista (Prueba de Sistema)",
        "company": "Sistema Automatizado",
        "score": 95,
        "platform": "InfoJobs + Indeed",
        "sector": "Tecnología e IA",
        "link": "https://www.infojobs.net/",
        "salary": "30.000 € / año",
        "location": "Alicante / Remoto"
    }
    return await send_telegram_notification(bot_token, chat_id, sample_job)
