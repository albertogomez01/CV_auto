import os
import sys
import json
import asyncio
import re
import io
import threading
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
from telegram.error import Conflict
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)

import database
from infojobs_scraper import search_jobs as search_infojobs
from indeed_scraper import search_indeed_httpx
from jooble_scraper import search_jooble
from adecco_scraper import search_adecco

load_dotenv()

# --- CONVERSATION STATES FOR ONBOARDING ---
WAITING_ROLE, WAITING_LOCATION, WAITING_CV = range(3)

# --- ONBOARDING CONVERSATION FLOW ---

async def start_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia el asistente conversacional interactivo paso a paso al recibir /start."""
    user = update.effective_user
    chat_id = str(update.effective_chat.id)
    first_name = user.first_name or "Usuario"

    existing_user = database.get_user(chat_id)

    msg = (
        f"¡Hola {first_name}! 👋 Bienvenid@ a <b>CV_auto</b>, tu asistente de búsqueda de empleo con Inteligencia Artificial.\n\n"
        "Te ayudaré a encontrar las mejores vacantes adaptadas a tu perfil en <b>InfoJobs, Indeed, Jooble y Adecco</b>.\n\n"
        "<b>Paso 1 de 3:</b> ¿Qué tipo de empleo o puesto buscas?\n"
        "<i>(ej. Programador Python, Auxiliar Administrativo, Camarero, Diseñador Gráfico, Mozo de Almacén)</i>"
    )

    if existing_user and existing_user.get("job_title"):
        msg += f"\n\n<i>Puesto actualmente guardado: {existing_user.get('job_title')} (Si respondes, se actualizará).</i>"

    await update.message.reply_text(msg, parse_mode="HTML")
    return WAITING_ROLE

async def process_role(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    role_text = update.message.text.strip()
    context.user_data["onboarding_role"] = role_text

    msg = (
        f"🎯 Puesto registrado: <b>{role_text}</b>\n\n"
        "<b>Paso 2 de 3:</b> ¿En qué ciudad o provincia buscas empleo?\n"
        "<i>(Escribe el nombre de tu ciudad o responde 'Remoto' si prefieres teletrabajo)</i>"
    )
    await update.message.reply_text(msg, parse_mode="HTML")
    return WAITING_LOCATION

async def process_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    loc_text = update.message.text.strip()
    context.user_data["onboarding_location"] = loc_text

    msg = (
        f"📍 Ubicación registrada: <b>{loc_text}</b>\n\n"
        "<b>Paso 3 de 3 (Final):</b> Adjunta aquí tu Currículum en <b>PDF</b> (o escribe directamente un resumen de tu experiencia laboral) para que la IA evalúe la compatibilidad con las vacantes."
    )
    await update.message.reply_text(msg, parse_mode="HTML")
    return WAITING_CV

async def process_cv(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    chat_id = str(update.effective_chat.id)
    username = user.username or user.first_name or "Usuario"

    role = context.user_data.get("onboarding_role", "Empleo General")
    location = context.user_data.get("onboarding_location", "Alicante")

    extracted_text = ""

    # Extraer texto de archivo PDF o TXT adjunto
    if update.message.document:
        doc = update.message.document
        file_name = doc.file_name or ""
        try:
            tg_file = await doc.get_file()
            file_bytes = await tg_file.download_as_bytearray()
            if file_name.lower().endswith(".pdf"):
                pdf_stream = io.BytesIO(file_bytes)
                reader = PdfReader(pdf_stream)
                pages_text = [page.extract_text() or "" for page in reader.pages]
                extracted_text = "\n".join(pages_text).strip()
            elif file_name.lower().endswith(".txt"):
                extracted_text = file_bytes.decode("utf-8", errors="ignore").strip()
        except Exception as e:
            print(f"[Onboarding CV Upload] Error: {e}")

    elif update.message.text:
        extracted_text = update.message.text.strip()

    if not extracted_text:
        extracted_text = f"Perfil profesional enfocado en {role} en {location}."

    # Insertar o actualizar registro de usuario en la base de datos SQLite
    user_rec = database.upsert_user(
        chat_id=chat_id,
        username=username,
        job_title=role,
        location=location,
        cv_text=extracted_text,
        active=1
    )

    preview = extracted_text[:200] + ("..." if len(extracted_text) > 200 else "")

    confirm_msg = (
        "🎉 <b>¡Registro Completado con Éxito!</b>\n\n"
        f"👤 <b>Usuario:</b> @{username}\n"
        f"🎯 <b>Puesto objetivo:</b> {role}\n"
        f"📍 <b>Ubicación:</b> {location}\n"
        f"📄 <b>Perfil CV ({len(extracted_text)} caracteres):</b>\n<i>\"{preview}\"</i>\n\n"
        "🔔 A partir de este momento, el sistema buscará periódicamente en <b>InfoJobs, Indeed, Jooble y Adecco</b> y te enviará las mejores ofertas a este chat.\n\n"
        "💡 <b>Comandos útiles:</b>\n"
        "• `/miperfil` - Revisa tu perfil registrado\n"
        "• `/pausar` - Pausa el envío de alertas\n"
        "• `/reanudar` - Reactiva las alertas\n"
        "• `/start` - Modifica tu registro paso a paso"
    )

    await update.message.reply_text(confirm_msg, parse_mode="HTML")
    return ConversationHandler.END

async def cancel_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Proceso cancelado. Escribe `/start` cuando desees iniciar de nuevo.", parse_mode="HTML")
    return ConversationHandler.END

# --- COMANDOS UTILITARIOS Y DE PERFIL ---

async def miperfil_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    user_rec = database.get_user(chat_id)

    if not user_rec or not user_rec.get("job_title"):
        await update.message.reply_text(
            "⚠️ Aún no estás registrado. Envía `/start` para iniciar el asistente de incorporación.",
            parse_mode="HTML"
        )
        return

    active_str = "🟢 Activo (Recibiendo alertas cada 30 min)" if user_rec.get("active") else "🔴 Pausado (Alertas suspendidas)"
    cv_text = user_rec.get("cv_text", "")
    cv_preview = cv_text[:250] + ("..." if len(cv_text) > 250 else "")

    profile_text = (
        "⚙️ <b>CONFIGURACIÓN DE TU PERFIL</b>\n\n"
        f"👤 <b>Usuario:</b> @{user_rec.get('username') or 'Sin alias'}\n"
        f"🆔 <b>Chat ID:</b> <code>{user_rec.get('chat_id')}</code>\n"
        f"🎯 <b>Puesto a buscar:</b> {user_rec.get('job_title')}\n"
        f"📍 <b>Ubicación:</b> {user_rec.get('location')}\n"
        f"🔔 <b>Estado de Alertas:</b> {active_str}\n\n"
        f"📄 <b>Perfil CV ({len(cv_text)} caracteres):</b>\n"
        f"<i>\"{cv_preview}\"</i>\n\n"
        "💡 <i>Usa `/pausar` o `/reanudar` para alternar alertas, o `/start` para reconfigurar tus datos.</i>"
    )
    await update.message.reply_text(profile_text, parse_mode="HTML")

async def pausar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    user_rec = database.get_user(chat_id)
    if user_rec:
        database.set_user_active(chat_id, 0)
        await update.message.reply_text(
            "🛑 <b>Alertas Pausadas.</b> No recibirás notificaciones periódicas hasta que envíes `/reanudar`.",
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text("⚠️ No estás registrado aún. Envía `/start` para comenzar.", parse_mode="HTML")

async def reanudar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    user_rec = database.get_user(chat_id)
    if user_rec:
        database.set_user_active(chat_id, 1)
        await update.message.reply_text(
            "▶️ <b>Alertas Reactivadas.</b> El bot continuará buscando ofertas para ti periódicamente.",
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text("⚠️ No estás registrado aún. Envía `/start` para comenzar.", parse_mode="HTML")

# --- CALLBACK QUERY HANDLER (Botonera interactiva 👍 / 👎) ---

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = str(query.message.chat_id)

    if data.startswith("interest_yes_"):
        job_hash = data.replace("interest_yes_", "")
        updated_job = database.update_job_status(job_hash, "interesado", user_id=chat_id)
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
        updated_job = database.update_job_status(job_hash, "descartada", user_id=chat_id)
        title = updated_job.get("title", "Oferta") if updated_job else "Oferta"
        company = updated_job.get("company", "") if updated_job else ""

        await query.answer("❌ Vacante descartada. No se te volverá a mostrar.")
        edited_text = (
            f"❌ <b>VACANTE DESCARTADA</b>\n\n"
            f"📌 <b>Puesto:</b> {title}\n"
            f"🏢 <b>Empresa:</b> {company}\n\n"
            f"<i>Has descartado esta propuesta. Ha sido guardada en la base de datos como descartada para no volver a mostrártela.</i>"
        )
        try:
            await query.edit_message_text(edited_text, parse_mode="HTML")
        except Exception:
            pass

# --- MANEJO DE CV EXTERNO AL ONBOARDING ---

async def handle_document_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc:
        return

    file_name = doc.file_name or ""
    chat_id = str(update.effective_chat.id)
    user = update.effective_user
    username = user.username or user.first_name or "Usuario"

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

        existing = database.get_user(chat_id)
        job_title = existing.get("job_title", "Desarrollador Python") if existing else "Desarrollador Python"
        location = existing.get("location", "Alicante") if existing else "Alicante"

        database.upsert_user(
            chat_id=chat_id,
            username=username,
            job_title=job_title,
            location=location,
            cv_text=extracted_text,
            active=1
        )

        preview = extracted_text[:250] + ("..." if len(extracted_text) > 250 else "")

        await update.message.reply_text(
            f"✅ <b>¡CV Actualizado y Guardado!</b>\n\n"
            f"<b>Vista previa ({len(extracted_text)} caracteres):</b>\n"
            f"<i>\"{preview}\"</i>\n\n"
            "La IA evaluará las siguientes ofertas comparándolas contra este nuevo perfil.",
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"[CV Upload Handler] Error: {e}")
        await update.message.reply_text(f"❌ Error al procesar el archivo: {str(e)}", parse_mode="HTML")

# --- HEALTH CHECK WEB SERVER FOR CLOUD HOSTING (RENDER / RAILWAY) ---

def start_health_server():
    if os.getenv("DISABLE_BOT_HEALTH_SERVER") == "1":
        return
    port_str = os.getenv("PORT", "").strip()
    if not port_str:
        return
    try:
        port = int(port_str)
        import uvicorn
        from fastapi import FastAPI

        health_app = FastAPI()

        @health_app.get("/")
        @health_app.get("/health")
        def health_check():
            return {"status": "ok", "bot": "CV_auto Telegram Bot"}

        def _run():
            print(f"🌐 Servidor Web de Health Check activo en puerto {port}")
            uvicorn.run(health_app, host="0.0.0.0", port=port, log_level="warning")

        t = threading.Thread(target=_run, daemon=True)
        t.start()
    except Exception as e:
        print(f"[Health Server Warning] No se pudo iniciar el servidor web: {e}")

# --- EXECUTION ENTRYPOINT ---

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "8929616203:AAGJ_XAfVo3AeKq_icY3HyJ0sN4ki5H0YVw").strip()
    if not token:
        print("❌ ERROR: Debes configurar la variable TELEGRAM_BOT_TOKEN en el archivo .env")
        sys.exit(1)

    print("🚀 Iniciando Bot Multiusuario de Telegram para Búsqueda de Empleo...")
    print(f"• Token Bot: {token[:8]}...{token[-4:]}")

    # Iniciar servidor de Health Check si Render asigna la variable PORT
    start_health_server()

    # Inicializar Base de Datos SQLite Multiusuario
    database.init_db()

    # Construir la aplicación Telegram
    app = ApplicationBuilder().token(token).build()

    # Configurar Asistente de Onboarding (/start)
    onboarding_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start_onboarding)],
        states={
            WAITING_ROLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_role)],
            WAITING_LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_location)],
            WAITING_CV: [
                MessageHandler(filters.Document.ALL, process_cv),
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_cv)
            ],
        },
        fallbacks=[CommandHandler("cancelar", cancel_onboarding)]
    )
    app.add_handler(onboarding_conv)

    # Comandos Utilitarios
    app.add_handler(CommandHandler("miperfil", miperfil_command))
    app.add_handler(CommandHandler("pausar", pausar_command))
    app.add_handler(CommandHandler("reanudar", reanudar_command))

    # Handlers de Botones e Ingesta Directa
    app.add_handler(CallbackQueryHandler(callback_query_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document_upload))

    # Manejador de errores para capturar Conflict suavemente sin spam de trazas
    async def handle_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        if isinstance(context.error, Conflict):
            print("⚠️ [Telegram Conflict] Se detectó otra conexión activa con la misma API Key. El bot reintentará automáticamente al quedar la conexión libre...")
            await asyncio.sleep(5)
        else:
            print(f"⚠️ [Telegram Warning] {context.error}")

    app.add_error_handler(handle_error)

    print("✅ Bot Multiusuario en ejecución. Presiona Ctrl+C para salir.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
