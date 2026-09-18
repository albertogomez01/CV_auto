import os
import sys
import json
import asyncio
import re
import io
from datetime import datetime
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv


# Ensure Proactor Event Loop Policy for Playwright on Windows
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from pypdf import PdfReader
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

import database
from infojobs_scraper import search_jobs as search_infojobs
from indeed_scraper import search_indeed_httpx
from jooble_scraper import search_jooble
from adecco_scraper import search_adecco

load_dotenv()

# --- CONFIGURATION & PATHS ---
CONFIG_FILE = "bot_config.json"
CV_FILE = "user_cv.txt"

DEFAULT_CONFIG = {
    "keywords": "Mozo, Auxiliar administrativo, Desarrollador Python",
    "location": "Alicante",
    "max_results": 10,
    "min_score": 50,
    "auto_enabled": False,
    "interval_seconds": 1800
}

def load_config() -> Dict[str, Any]:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                return {**DEFAULT_CONFIG, **config}
        except Exception as e:
            print(f"[Config] Error leyendo config: {e}")
    return DEFAULT_CONFIG.copy()

def save_config(config: Dict[str, Any]):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Config] Error guardando config: {e}")

def load_cv_text() -> str:
    if os.path.exists(CV_FILE):
        try:
            with open(CV_FILE, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    return ""

def save_cv_text(text: str):
    with open(CV_FILE, "w", encoding="utf-8") as f:
        f.write(text)

# --- GEMINI SCORING ENGINE ---
def evaluate_job_match(job: Dict[str, Any], cv_text: str) -> Dict[str, Any]:
    """
    Calcula el % de coincidencia (score) del CV con la oferta usando Gemini AI.
    Si no hay API key o falla Gemini, se utiliza una heurística inteligente de respaldo.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    title = job.get("title", "")
    company = job.get("company", "")
    description = job.get("description", "")
    sector = job.get("sector", "")

    if api_key and cv_text:
        try:
            # Intento con google-genai o google.generativeai
            prompt = f"""
Eres un evaluador de selección de personal. Compara el perfil profesional del candidato con la vacante.

PERFIL CV CANDIDATO:
{cv_text[:3000]}

VACANTE A EVALUAR:
- Título: {title}
- Empresa: {company}
- Sector: {sector}
- Descripción: {description[:1500]}

Calcula una puntuación de coincidencia entre 0 y 100 basada en habilidades, experiencia y requisitos.
Responde ÚNICAMENTE en formato JSON:
{{
  "score": 85,
  "reasoning": "Breve explicación en una frase..."
}}
"""
            try:
                from google import genai
                client = genai.Client(api_key=api_key)
                response = client.models.generate_content(
                    model="gemini-1.5-flash",
                    contents=prompt
                )
                res_text = response.text
            except Exception:
                import google.generativeai as genai_old
                genai_old.configure(api_key=api_key)
                model = genai_old.GenerativeModel("gemini-1.5-flash")
                response = model.generate_content(prompt)
                res_text = response.text

            # Parse JSON response
            clean_json = re.sub(r'```json\s*|\s*```', '', res_text).strip()
            data = json.loads(clean_json)
            return {
                "score": int(data.get("score", 70)),
                "reasoning": data.get("reasoning", "Evaluado con Gemini AI.")
            }
        except Exception as e:
            print(f"[Gemini Scoring] Exception: {e}. Usando scoring heurístico...")

    # Scoring heurístico de respaldo (si no hay API key o la llamada falla)
    if not cv_text:
        return {"score": 75, "reasoning": "Puntuación base (Suba su CV para personalización)."}

    cv_words = set(re.findall(r'\w+', cv_text.lower()))
    job_words = set(re.findall(r'\w+', f"{title} {description} {sector}".lower()))
    
    # Palabras clave comunes descartadas
    stopwords = {"de", "la", "el", "en", "y", "a", "los", "del", "se", "con", "un", "para", "por", "las", "su", "para"}
    cv_keywords = {w for w in cv_words if len(w) > 3 and w not in stopwords}
    job_keywords = {w for w in job_words if len(w) > 3 and w not in stopwords}

    if not job_keywords:
        return {"score": 70, "reasoning": "Coincidencia estimada."}

    matches = cv_keywords.intersection(job_keywords)
    match_ratio = len(matches) / max(1, len(job_keywords))
    calculated_score = min(98, max(55, int(60 + match_ratio * 40)))

    return {
        "score": calculated_score,
        "reasoning": f"Coincidencia basada en palabras clave del perfil ({len(matches)} términos)."
    }

# --- SEARCH & PIPELINE ---
async def perform_search_and_notify(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    is_auto: bool = False
) -> int:
    """
    Ejecuta la búsqueda multirrubro (InfoJobs, Indeed, Jooble),
    filtra repetidos contra SQLite database, evalúa con Gemini y envía las alertas a Telegram.
    """
    config = load_config()
    cv_text = load_cv_text()
    keywords = config.get("keywords", "Mozo, Auxiliar administrativo, Desarrollador Python")
    location = config.get("location", "Alicante")
    max_results = config.get("max_results", 10)

    all_jobs: List[Dict[str, Any]] = []

    # 1. Scraping InfoJobs (Playwright)
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
        print(f"[Search Pipeline] Error InfoJobs: {e}")

    # 2. Scraping Indeed (HTTP)
    try:
        ind_jobs = await search_indeed_httpx(keywords=keywords, location=location, max_results=max_results)
        for j in ind_jobs:
            j["platform"] = "Indeed"
        all_jobs.extend(ind_jobs)
    except Exception as e:
        print(f"[Search Pipeline] Error Indeed: {e}")

    # 3. Scraping Jooble (HTTP)
    try:
        joo_jobs = await search_jooble(keywords=keywords, location=location, max_results=max_results)
        for j in joo_jobs:
            j["platform"] = "Jooble"
        all_jobs.extend(joo_jobs)
    except Exception as e:
        print(f"[Search Pipeline] Error Jooble: {e}")

    # 4. Scraping Adecco (Playwright)
    try:
        adecco_jobs = await search_adecco(keywords=keywords, location=location, max_results=max_results, headless=True)
        for j in adecco_jobs:
            j["platform"] = "Adecco"
        all_jobs.extend(adecco_jobs)
    except Exception as e:
        print(f"[Search Pipeline] Error Adecco: {e}")

    new_offers_count = 0

    for job in all_jobs:
        title = job.get("title", "Oferta sin título")
        company = job.get("company", "Empresa no especificada")
        link = job.get("link", "")
        job_id = job.get("job_id") or link or f"{title}_{company}"
        if not job_id:
            continue

        # FILTRO DE DEDUPLICACIÓN ANTI-SPAM MULTINIVEL (ID, URL, TÍTULO+EMPRESA)
        if database.is_job_processed(job_id=job_id, link=link, title=title, company=company):
            continue

        # Evaluar coincidencia con Gemini / IA
        eval_result = evaluate_job_match(job, cv_text)
        score = eval_result["score"]
        reasoning = eval_result["reasoning"]
        job["score"] = score

        loc = job.get("location") or location
        salary = job.get("salary") or "No especificado"
        platform = job.get("platform", "Multiplataforma")
        if not link:
            link = "https://www.infojobs.net/"

        # Registrar en la base de datos SQLite como notificada
        database.record_application(
            job_id=job_id,
            title=title,
            company=company,
            link=link,
            score=score,
            status="notified_telegram",
            salary=salary,
            location=loc,
            platform=platform
        )


        new_offers_count += 1

        # Formato de Alerta Enriquecida
        msg_text = (
            f"🚨 <b>¡NUEVA VACANTE DESTACADA ({score}% Coincidencia)!</b>\n\n"
            f"📌 <b>Puesto:</b> {title}\n"
            f"🏢 <b>Empresa:</b> {company}\n"
            f"📍 <b>Ubicación:</b> {loc}\n"
            f"💰 <b>Salario:</b> {salary}\n"
            f"🏷️ <b>Plataforma:</b> {platform}\n"
            f"💡 <i>{reasoning}</i>"
        )

        import hashlib
        job_hash = hashlib.md5(str(job_id).encode("utf-8")).hexdigest()[:16]

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("👍 Me interesa", callback_data=f"interest_yes_{job_hash}"),
                InlineKeyboardButton("👎 No me interesa", callback_data=f"interest_no_{job_hash}")
            ],
            [InlineKeyboardButton("🔗 Ver Oferta y Postular", url=link)]
        ])

        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=msg_text,
                parse_mode="HTML",
                reply_markup=keyboard,
                disable_web_page_preview=False
            )
            await asyncio.sleep(0.5) # Evitar rate-limits de Telegram
        except Exception as e:
            print(f"[Telegram Alert] Error enviando mensaje: {e}")

    return new_offers_count

# --- BACKGROUND JOB (JOBQUEUE 30 MIN) ---
async def auto_search_job_callback(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id = job.chat_id
    print(f"[Autopiloto JobQueue] Ejecutando barrido automático cada 30 min para chat_id {chat_id}...")
    count = await perform_search_and_notify(context=context, chat_id=chat_id, is_auto=True)
    print(f"[Autopiloto JobQueue] Barrido completado. Nuevas ofertas enviadas: {count}")

# --- KEYBOARD MENUS ---
def build_main_keyboard(auto_enabled: bool) -> InlineKeyboardMarkup:
    auto_label = "🔴 Pausar Autopiloto (30 min)" if auto_enabled else "⚡ Activar Autopiloto (30 min)"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Búsqueda Manual Inmediata", callback_data="menu_manual_search")],
        [InlineKeyboardButton(auto_label, callback_data="menu_toggle_auto")],
        [
            InlineKeyboardButton("⚙️ Parámetros", callback_data="menu_settings"),
            InlineKeyboardButton("📊 Estadísticas", callback_data="menu_stats")
        ],
        [InlineKeyboardButton("📄 Mi CV / Subir CV", callback_data="menu_cv")]
    ])

def build_settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📍 Cambiar Ciudad / Ubicación", callback_data="set_location")],
        [InlineKeyboardButton("🏷️ Cambiar Palabras Clave / Sector", callback_data="set_keywords")],
        [InlineKeyboardButton("🔢 Cambiar Cantidad Máxima por Búsqueda", callback_data="set_max_results")],
        [InlineKeyboardButton("⬅️ Volver al Menú Principal", callback_data="menu_main")]
    ])

# --- COMMAND HANDLERS ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config = load_config()
    chat_id = update.effective_chat.id
    
    welcome_text = (
        "🤖 <b>Bot Autónomo de Búsqueda de Empleo</b>\n\n"
        "¡Bienvenido! Este bot monitoriza continuamente InfoJobs, Indeed y Jooble, "
        "descartando ofertas repetidas y notificándote únicamente vacantes nuevas con coincidencia de IA.\n\n"
        "<b>Configuración Actual:</b>\n"
        f"• <b>Palabras Clave:</b> {config.get('keywords')}\n"
        f"• <b>Ubicación:</b> {config.get('location')}\n"
        f"• <b>Límite por Búsqueda:</b> {config.get('max_results')} ofertas\n"
        f"• <b>Autopiloto 30 min:</b> {'✅ ACTIVO' if config.get('auto_enabled') else '❌ PAUSADO'}\n\n"
        "Selecciona una opción del menú interactivo:"
    )
    
    keyboard = build_main_keyboard(config.get("auto_enabled", False))
    await update.message.reply_text(welcome_text, parse_mode="HTML", reply_markup=keyboard)

async def iniciar_auto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    config = load_config()
    
    # Comprobar si ya está programado en la JobQueue
    current_jobs = context.job_queue.get_jobs_by_name(f"auto_search_{chat_id}")
    if not current_jobs:
        context.job_queue.run_repeating(
            auto_search_job_callback,
            interval=config.get("interval_seconds", 1800),
            first=10,
            chat_id=chat_id,
            name=f"auto_search_{chat_id}"
        )
    
    config["auto_enabled"] = True
    save_config(config)

    msg = "⚡ <b>Autopiloto Activado</b>\n\nEl bot realizará un barrido silencioso cada 30 minutos y te enviará únicamente las ofertas nuevas que coincidan con tu perfil."
    keyboard = build_main_keyboard(True)
    if update.callback_query:
        await update.callback_query.edit_message_text(msg, parse_mode="HTML", reply_markup=keyboard)
    else:
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=keyboard)

async def pausar_auto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    config = load_config()

    current_jobs = context.job_queue.get_jobs_by_name(f"auto_search_{chat_id}")
    for j in current_jobs:
        j.schedule_removal()

    config["auto_enabled"] = False
    save_config(config)

    msg = "🔴 <b>Autopiloto Pausado</b>\n\nLas alertas automáticas periódicas han sido pausadas. Puedes lanzar búsquedas manuales cuando lo desees."
    keyboard = build_main_keyboard(False)
    if update.callback_query:
        await update.callback_query.edit_message_text(msg, parse_mode="HTML", reply_markup=keyboard)
    else:
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=keyboard)

# --- CALLBACK QUERY HANDLER ---
async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = query.message.chat_id
    config = load_config()

    if data.startswith("interest_yes_"):
        job_hash = data.replace("interest_yes_", "")
        updated_job = database.update_job_status(job_hash, "interesado")
        title = updated_job.get("title", "Oferta") if updated_job else "Oferta"
        company = updated_job.get("company", "") if updated_job else ""
        link = updated_job.get("link", "#") if updated_job else "#"
        
        await query.answer("⭐ Marcada como INTERESANTE. ¡Guardada en tu historial!")
        edited_text = (
            f"⭐ <b>VACANTE MARCADA COMO INTERESANTE</b>\n\n"
            f"📌 <b>Puesto:</b> {title}\n"
            f"🏢 <b>Empresa:</b> {company}\n\n"
            f"<i>Esta vacante ha sido destacada en tu historial de candidaturas.</i>\n"
            f"🔗 <a href='{link}'>Ver Oferta en la web</a>"
        )
        try:
            await query.edit_message_text(edited_text, parse_mode="HTML", disable_web_page_preview=False)
        except Exception:
            pass

    elif data.startswith("interest_no_"):
        job_hash = data.replace("interest_no_", "")
        updated_job = database.update_job_status(job_hash, "descartada")
        title = updated_job.get("title", "Oferta") if updated_job else "Oferta"
        company = updated_job.get("company", "") if updated_job else ""
        
        await query.answer("❌ Vacante descartada. No se te volverá a mostrar.")
        edited_text = (
            f"❌ <b>VACANTE DESCARTADA (No volverá a salir)</b>\n\n"
            f"📌 <b>Puesto:</b> {title}\n"
            f"🏢 <b>Empresa:</b> {company}\n\n"
            f"<i>Has descartado esta propuesta. Ha sido guardada en la base de datos como descartada para que el sistema no vuelva a mostrártela.</i>"
        )
        try:
            await query.edit_message_text(edited_text, parse_mode="HTML")
        except Exception:
            pass

    elif data == "menu_main":
        keyboard = build_main_keyboard(config.get("auto_enabled", False))
        await query.edit_message_text("🤖 <b>Menú Principal del Bot de Empleo</b>\n\nSelecciona una opción:", parse_mode="HTML", reply_markup=keyboard)

    elif data == "menu_toggle_auto":
        if config.get("auto_enabled", False):
            await pausar_auto_command(update, context)
        else:
            await iniciar_auto_command(update, context)

    elif data == "menu_manual_search":
        await query.edit_message_text("⏳ <b>Iniciando búsqueda manual multirrubro...</b>\n\nExplorando InfoJobs, Indeed y Jooble. Por favor, espera unos instantes...", parse_mode="HTML")
        count = await perform_search_and_notify(context=context, chat_id=chat_id, is_auto=False)
        keyboard = build_main_keyboard(config.get("auto_enabled", False))
        if count == 0:
            res_msg = "✅ <b>Búsqueda completada.</b>\n\nNo se encontraron vacantes nuevas desatendidas (todas las detectadas ya se enviaron previamente o no hay nuevos resultados)."
        else:
            res_msg = f"✅ <b>Búsqueda completada.</b>\n\nSe han enviado <b>{count} nueva(s) oferta(s)</b> a este chat."
        await context.bot.send_message(chat_id=chat_id, text=res_msg, parse_mode="HTML", reply_markup=keyboard)

    elif data == "menu_settings":
        keyboard = build_settings_keyboard()
        text = (
            "⚙️ <b>Parámetros de Búsqueda</b>\n\n"
            f"📍 <b>Ubicación:</b> {config.get('location')}\n"
            f"🏷️ <b>Palabras Clave:</b> {config.get('keywords')}\n"
            f"🔢 <b>Máximo de Ofertas:</b> {config.get('max_results')}\n\n"
            "Elige el parámetro que deseas modificar:"
        )
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

    elif data == "set_location":
        context.user_data["awaiting_input"] = "location"
        await query.edit_message_text("📍 <b>Modificar Ubicación</b>\n\nResponde a este mensaje escribiendo el nombre de la ciudad o provincia (ejemplo: <code>Alicante</code> o <code>Madrid</code>):", parse_mode="HTML")

    elif data == "set_keywords":
        context.user_data["awaiting_input"] = "keywords"
        await query.edit_message_text("🏷️ <b>Modificar Palabras Clave / Sector</b>\n\nResponde a este mensaje escribiendo los puestos o palabras clave separados por comas (ejemplo: <code>Mozo, Auxiliar administrativo, Python</code>):", parse_mode="HTML")

    elif data == "set_max_results":
        context.user_data["awaiting_input"] = "max_results"
        await query.edit_message_text("🔢 <b>Modificar Cantidad Máxima</b>\n\nResponde a este mensaje escribiendo un número (ejemplo: <code>10</code> o <code>20</code>):", parse_mode="HTML")

    elif data == "menu_stats":
        all_apps = database.get_all_applications(limit=500)
        total_recorded = len(all_apps)
        today_str = datetime.now().strftime("%Y-%m-%d")
        today_count = sum(1 for a in all_apps if str(a.get("date_applied", "")).startswith(today_str))
        cv_text = load_cv_text()
        has_cv = bool(cv_text)

        stats_text = (
            "📊 <b>Estado y Estadísticas del Bot</b>\n\n"
            f"🤖 <b>Estado del Autopiloto:</b> {'✅ ACTIVO (30 min)' if config.get('auto_enabled') else '🔴 PAUSADO'}\n"
            f"📄 <b>Perfil CV Cargado:</b> {'✅ REGISTRADO (' + str(len(cv_text)) + ' caracteres)' if has_cv else '⚠️ NO CONFIGURADO'}\n"
            f"📩 <b>Ofertas detectadas y notificadas hoy:</b> {today_count}\n"
            f"💾 <b>Histórico en Base de Datos:</b> {total_recorded} vacantes registadas\n\n"
            f"<b>Filtros Activos:</b>\n"
            f"• Ubicación: {config.get('location')}\n"
            f"• Búsqueda: {config.get('keywords')}"
        )
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Volver al Menú", callback_data="menu_main")]])
        await query.edit_message_text(stats_text, parse_mode="HTML", reply_markup=keyboard)

    elif data == "menu_cv":
        cv_text = load_cv_text()
        if cv_text:
            preview = cv_text[:300] + ("..." if len(cv_text) > 300 else "")
            cv_msg = (
                "📄 <b>Gestión de CV / Perfil Profesional</b>\n\n"
                "✅ <b>CV Registrado Correctamente:</b>\n"
                f"<i>\"{preview}\"</i>\n\n"
                "💡 Para actualizarlo, simplemente sube un archivo <b>PDF</b>, <b>TXT</b> o escribe directamente tu CV en este chat."
            )
        else:
            cv_msg = (
                "📄 <b>Gestión de CV / Perfil Profesional</b>\n\n"
                "⚠️ <b>Aún no has subido tu CV.</b>\n\n"
                "Sube un archivo <b>PDF</b>, <b>TXT</b> o escribe tus habilidades e historial laboral directamente en este chat para que la IA (Gemini) calcule el % de coincidencia con las ofertas."
            )
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Volver al Menú", callback_data="menu_main")]])
        await query.edit_message_text(cv_msg, parse_mode="HTML", reply_markup=keyboard)

# --- MESSAGE HANDLERS (CV INGESTION & SETTINGS INPUT) ---
async def handle_document_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc:
        return

    file_name = doc.file_name or ""
    chat_id = update.effective_chat.id
    
    await update.message.reply_text("📄 Recibiendo archivo de CV... Procesando documento...", parse_mode="HTML")

    try:
        tg_file = await doc.get_file()
        file_bytes = await tg_file.download_as_bytearray()
        extracted_text = ""

        if file_name.lower().endswith(".pdf"):
            pdf_stream = io.BytesIO(file_bytes)
            reader = PdfReader(pdf_stream)
            pages_text = [page.extract_text() or "" for page in reader.pages]
            extracted_text = "\n".join(pages_text).strip()
        elif file_name.lower().endswith(".txt"):
            extracted_text = file_bytes.decode("utf-8", errors="ignore").strip()
        else:
            await update.message.reply_text("⚠️ Formato no soportado. Por favor, sube un archivo <b>.pdf</b> o <b>.txt</b>.", parse_mode="HTML")
            return

        if not extracted_text:
            await update.message.reply_text("⚠️ No se pudo extraer texto legible del documento.", parse_mode="HTML")
            return

        save_cv_text(extracted_text)
        preview = extracted_text[:250] + ("..." if len(extracted_text) > 250 else "")
        keyboard = build_main_keyboard(load_config().get("auto_enabled", False))

        await update.message.reply_text(
            f"✅ <b>¡CV Procesado y Guardado con Éxito!</b>\n\n"
            f"<b>Vista previa del perfil extraído ({len(extracted_text)} caracteres):</b>\n"
            f"<i>\"{preview}\"</i>\n\n"
            "A partir de ahora, la IA (Gemini) calculará el % de coincidencia de cada oferta contra este perfil.",
            parse_mode="HTML",
            reply_markup=keyboard
        )
    except Exception as e:
        print(f"[CV Upload Handler] Error: {e}")
        await update.message.reply_text(f"❌ Error al procesar el archivo: {str(e)}", parse_mode="HTML")

async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    awaiting = context.user_data.get("awaiting_input")
    config = load_config()

    if awaiting == "location":
        config["location"] = text
        save_config(config)
        context.user_data["awaiting_input"] = None
        keyboard = build_main_keyboard(config.get("auto_enabled", False))
        await update.message.reply_text(f"✅ <b>Ubicación actualizada:</b> <code>{text}</code>", parse_mode="HTML", reply_markup=keyboard)

    elif awaiting == "keywords":
        config["keywords"] = text
        save_config(config)
        context.user_data["awaiting_input"] = None
        keyboard = build_main_keyboard(config.get("auto_enabled", False))
        await update.message.reply_text(f"✅ <b>Palabras Clave actualizadas:</b> <code>{text}</code>", parse_mode="HTML", reply_markup=keyboard)

    elif awaiting == "max_results":
        if text.isdigit() and int(text) > 0:
            config["max_results"] = int(text)
            save_config(config)
            context.user_data["awaiting_input"] = None
            keyboard = build_main_keyboard(config.get("auto_enabled", False))
            await update.message.reply_text(f"✅ <b>Máximo de ofertas actualizado:</b> <code>{text}</code>", parse_mode="HTML", reply_markup=keyboard)
        else:
            await update.message.reply_text("⚠️ Por favor, introduce un número válido mayor que 0.", parse_mode="HTML")

    else:
        # Si el texto es largo (ej. > 80 caracteres), asumimos que el usuario está enviando su CV en texto plano
        if len(text) > 80:
            save_cv_text(text)
            preview = text[:250] + ("..." if len(text) > 250 else "")
            keyboard = build_main_keyboard(config.get("auto_enabled", False))
            await update.message.reply_text(
                f"✅ <b>¡CV en texto guardado correctamente!</b>\n\n"
                f"<b>Vista previa ({len(text)} caracteres):</b>\n"
                f"<i>\"{preview}\"</i>",
                parse_mode="HTML",
                reply_markup=keyboard
            )
        else:
            keyboard = build_main_keyboard(config.get("auto_enabled", False))
            await update.message.reply_text(
                "Escribe `/start` o utiliza el menú de botones interactivos para controlar el bot.",
                parse_mode="HTML",
                reply_markup=keyboard
            )

# --- MAIN EXECUTION ---
def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("❌ ERROR: Debes configurar la variable TELEGRAM_BOT_TOKEN en el archivo .env")
        sys.exit(1)

    print("🚀 Iniciando Bot Autónomo de Telegram para Búsqueda de Empleo...")
    print(f"• Token Bot: {token[:8]}...{token[-4:]}")
    
    # Inicializar Base de Datos SQLite
    database.init_db()
    
    config = load_config()

    # Construir la aplicación con python-telegram-bot
    app = ApplicationBuilder().token(token).build()

    # Registrar Handlers de Comandos
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("iniciar_auto", iniciar_auto_command))
    app.add_handler(CommandHandler("pausar_auto", pausar_auto_command))

    # Registrar Handler de Botones Interactivos (CallbackQueries)
    app.add_handler(CallbackQueryHandler(callback_query_handler))

    # Registrar Handlers de Mensajes y Documentos (CV Ingestion / Text Input)
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document_upload))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_messages))

    # Si el autopiloto estaba activo previamente, reprogramar el job en la JobQueue
    if config.get("auto_enabled", False):
        default_chat = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        if default_chat and default_chat.isdigit():
            cid = int(default_chat)
            app.job_queue.run_repeating(
                auto_search_job_callback,
                interval=config.get("interval_seconds", 1800),
                first=10,
                chat_id=cid,
                name=f"auto_search_{cid}"
            )
            print(f"⚡ Autopiloto restaurado para el chat ID {cid} (cada 30 min).")

    print("✅ Bot de Telegram en ejecución. Presiona Ctrl+C para salir.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
