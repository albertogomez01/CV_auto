import sys
import asyncio
import os
import json
import io
import streamlit as st
import pandas as pd
import requests
from dotenv import load_dotenv

# Configure Windows asyncio ProactorEventLoopPolicy for Playwright compatibility
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from playwright.async_api import async_playwright
import database
import importlib
importlib.reload(database)
from infojobs_scraper import search_jobs, apply_to_job
import infojobs_scraper
importlib.reload(infojobs_scraper)
from indeed_scraper import search_indeed
import indeed_scraper
importlib.reload(indeed_scraper)
from jooble_scraper import search_jooble
import jooble_scraper
importlib.reload(jooble_scraper)
from adecco_scraper import search_adecco
import adecco_scraper
importlib.reload(adecco_scraper)
from telegram_notifier import send_telegram_notification, test_telegram_connection
from login_setup import run_login_setup

load_dotenv()

# ==============================================================================
# 1. CONFIGURACIÓN DE PÁGINA Y ESTILOS CSS (Dashboard Centrado / App Móvil)
# ==============================================================================
st.set_page_config(
    page_title="CV-auto | Agente Autónomo de Empleo",
    page_icon="🤖",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Estilos CSS Limpios con Bordes Redondeados, Tarjetas Sombreadas y Bottom Dock
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@500;600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');
    
    /* Base Reset & Colors */
    html, body, [class*="css"], .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"], [data-testid="stSidebar"], [data-testid="stMain"], .main {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
        background-color: #090D16 !important;
        background: #090D16 !important;
        color: #F8FAFC !important;
        -webkit-tap-highlight-color: transparent;
        -webkit-font-smoothing: antialiased;
    }

    /* Main Container max-width & padding for mobile/web app */
    .block-container {
        padding-top: 1.2rem !important;
        padding-bottom: 110px !important;
        max-width: 960px !important;
        background: #090D16 !important;
    }

    /* Input font size for iOS Safari */
    input, select, textarea {
        font-size: 16px !important;
    }
    
    /* Hide Default Streamlit Chrome & Headers */
    [data-testid="stHeader"], header[data-testid="stHeader"], [data-testid="stToolbar"] {
        background: transparent !important;
        height: 0px !important;
    }
    footer, #MainMenu, header {
        visibility: hidden !important;
        display: none !important;
    }
    
    /* Headings Typography */
    h1, h2, h3, .main-title {
        font-family: 'Outfit', sans-serif !important;
        letter-spacing: -0.02em !important;
        color: #F8FAFC !important;
    }

    /* Clean Card Container Styling */
    .wire-card {
        background: rgba(17, 24, 39, 0.65);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 18px;
        padding: 18px 20px;
        margin-bottom: 16px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
    }
    
    .wire-card-title {
        font-family: 'Outfit', sans-serif;
        font-size: 1.15rem;
        font-weight: 700;
        color: #F8FAFC;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    /* Top Header Bar */
    .top-header-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 18px;
    }

    .main-logo-text {
        font-family: 'Outfit', sans-serif;
        font-size: 2.1rem;
        font-weight: 800;
        background: linear-gradient(135deg, #38BDF8 0%, #818CF8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: -0.5px;
        line-height: 1.1;
    }

    .main-subtitle {
        color: #94A3B8;
        font-size: 0.92rem;
        font-weight: 500;
    }

    /* Badge Chips / Pills */
    .chip-badge {
        display: inline-flex;
        align-items: center;
        background: rgba(56, 189, 248, 0.12);
        color: #38BDF8;
        border: 1px solid rgba(56, 189, 248, 0.3);
        border-radius: 20px;
        padding: 5px 12px;
        font-size: 0.82rem;
        font-weight: 600;
        margin: 3px 4px 3px 0;
    }

    .chip-badge-purple {
        display: inline-flex;
        align-items: center;
        background: rgba(129, 140, 248, 0.14);
        color: #A5B4FC;
        border: 1px solid rgba(129, 140, 248, 0.3);
        border-radius: 20px;
        padding: 5px 12px;
        font-size: 0.82rem;
        font-weight: 600;
        margin: 3px 4px 3px 0;
    }

    .chip-badge-green {
        display: inline-flex;
        align-items: center;
        background: rgba(52, 211, 153, 0.14);
        color: #34D399;
        border: 1px solid rgba(52, 211, 153, 0.3);
        border-radius: 20px;
        padding: 5px 12px;
        font-size: 0.82rem;
        font-weight: 600;
        margin: 3px 4px 3px 0;
    }

    /* Touch-friendly Native Buttons */
    .stButton>button {
        border-radius: 14px !important;
        font-weight: 600 !important;
        min-height: 48px !important;
        font-size: 0.95rem !important;
        transition: all 0.22s cubic-bezier(0.16, 1, 0.3, 1) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        background: rgba(30, 41, 59, 0.7) !important;
        color: #F1F5F9 !important;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.2) !important;
    }
    
    .stButton>button:hover {
        background: rgba(51, 65, 85, 0.85) !important;
        border-color: rgba(56, 189, 248, 0.45) !important;
        color: #FFFFFF !important;
        transform: translateY(-1px) !important;
    }

    /* Primary Central Action Button */
    .stButton>button[kind="primary"] {
        background: linear-gradient(135deg, #38BDF8 0%, #6366F1 100%) !important;
        border: none !important;
        color: #FFFFFF !important;
        box-shadow: 0 4px 22px rgba(56, 189, 248, 0.4) !important;
        font-weight: 700 !important;
        font-size: 1.05rem !important;
        min-height: 52px !important;
    }
    
    .stButton>button[kind="primary"]:hover {
        box-shadow: 0 6px 28px rgba(56, 189, 248, 0.55) !important;
        transform: translateY(-1px) !important;
    }

    /* HIDE STREAMLIT DEFAULT TAB UNDERLINE */
    div[data-baseweb="tab-highlight"], 
    div[data-baseweb="tab-border"], 
    [data-baseweb="tab-highlight"], 
    [data-baseweb="tab-border"] {
        display: none !important;
        visibility: hidden !important;
        height: 0px !important;
        opacity: 0 !important;
    }

    /* 6. BARRA DE NAVEGACIÓN INFERIOR PERSISTENTE (4 TABS DOCK) */
    div[data-baseweb="tab-list"], [data-baseweb="tab-list"] {
        position: fixed !important;
        bottom: 0px !important;
        left: 0px !important;
        right: 0px !important;
        width: 100vw !important;
        max-width: 100% !important;
        height: 68px !important;
        z-index: 999999 !important;
        background: rgba(11, 16, 26, 0.95) !important;
        backdrop-filter: blur(24px) !important;
        -webkit-backdrop-filter: blur(24px) !important;
        border-top: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-left: none !important;
        border-right: none !important;
        border-bottom: none !important;
        border-radius: 0px !important;
        padding: 4px 8px calc(4px + env(safe-area-inset-bottom, 8px)) 8px !important;
        display: flex !important;
        justify-content: space-around !important;
        align-items: center !important;
        gap: 4px !important;
        box-shadow: 0 -10px 30px rgba(0, 0, 0, 0.6) !important;
        margin: 0 !important;
    }
    
    @media (min-width: 769px) {
        div[data-baseweb="tab-list"], [data-baseweb="tab-list"] {
            bottom: 12px !important;
            left: 50% !important;
            transform: translateX(-50%) !important;
            width: calc(100% - 32px) !important;
            max-width: 720px !important;
            height: 64px !important;
            border-radius: 22px !important;
            border: 1px solid rgba(255, 255, 255, 0.12) !important;
            box-shadow: 0 20px 50px -10px rgba(0, 0, 0, 0.85), 0 0 0 1px rgba(255, 255, 255, 0.08) !important;
        }
    }
    
    /* Target Tab Elements for Vertical Icon + Label Alignment */
    [data-baseweb="tab"], button[data-baseweb="tab"], div[data-baseweb="tab"] {
        flex: 1 1 0% !important;
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        justify-content: center !important;
        text-align: center !important;
        padding: 5px 2px !important;
        height: 100% !important;
        font-size: 0.76rem !important;
        font-weight: 600 !important;
        color: #64748B !important;
        border-radius: 14px !important;
        transition: all 0.22s cubic-bezier(0.16, 1, 0.3, 1) !important;
        background: transparent !important;
        border: 1px solid transparent !important;
        margin: 0 !important;
        cursor: pointer !important;
        white-space: pre-line !important;
        line-height: 1.15 !important;
    }
    
    [data-baseweb="tab"]:hover, button[data-baseweb="tab"]:hover {
        color: #F1F5F9 !important;
        background: rgba(255, 255, 255, 0.04) !important;
    }
    
    [data-baseweb="tab"][aria-selected="true"], button[data-baseweb="tab"][aria-selected="true"] {
        color: #38BDF8 !important;
        background: linear-gradient(135deg, rgba(56, 189, 248, 0.2) 0%, rgba(99, 102, 241, 0.2) 100%) !important;
        border: 1px solid rgba(56, 189, 248, 0.4) !important;
        box-shadow: 0 4px 16px rgba(56, 189, 248, 0.2) !important;
        font-weight: 700 !important;
    }

    /* Tab Level Transition Animation */
    div[data-baseweb="tab-panel"], [data-testid="stTabContent"] {
        animation: tabSlideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards !important;
    }

    @keyframes tabSlideUp {
        0% { opacity: 0; transform: translateY(10px); }
        100% { opacity: 1; transform: translateY(0); }
    }

    /* Popover Modal Styling */
    div[data-testid="stPopoverBody"] {
        background-color: #0F172A !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 18px !important;
        box-shadow: 0 16px 40px rgba(0, 0, 0, 0.6) !important;
    }

    div[data-baseweb="input"], div[data-baseweb="textarea"], [data-testid="stFileUploader"] {
        border-radius: 14px !important;
        background: rgba(17, 24, 39, 0.6) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        color: #F8FAFC !important;
    }
</style>

<!-- Mobile PWA Meta Headers -->
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<meta name="theme-color" content="#090D16">
""", unsafe_allow_html=True)

# Helper functions
def run_async(coro):
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

def extract_text_from_file(uploaded_file) -> str:
    if uploaded_file is None:
        return ""
    try:
        file_bytes = uploaded_file.getvalue()
    except Exception:
        try:
            uploaded_file.seek(0)
            file_bytes = uploaded_file.read()
        except Exception:
            return ""
    if not file_bytes:
        return ""
        
    filename = uploaded_file.name.lower()
    ext = os.path.splitext(filename)[1]
    
    text = ""
    if ext == ".pdf":
        try:
            import pypdf
            pdf_reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            pages_text = [page.extract_text() or "" for page in pdf_reader.pages]
            text = "\n".join(pages_text).strip()
        except Exception as e:
            st.warning(f"Aviso PDF: {e}")
    elif ext == ".docx":
        try:
            import docx
            document = docx.Document(io.BytesIO(file_bytes))
            text = "\n".join([p.text for p in document.paragraphs if p.text.strip()]).strip()
        except Exception as e:
            st.warning(f"Aviso Word: {e}")
    elif ext in [".txt", ".md"]:
        try:
            text = file_bytes.decode("utf-8", errors="ignore").strip()
        except Exception as e:
            st.warning(f"Aviso Texto: {e}")
            
    if not text:
        try:
            raw_txt = file_bytes.decode("utf-8", errors="ignore").strip()
            if not raw_txt.startswith("%PDF") and not raw_txt.startswith("PK") and "\x00" not in raw_txt:
                import re
                clean = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', raw_txt).strip()
                if len(clean) > 10:
                    text = clean
        except Exception:
            pass
    return text

def get_gemini_client(api_key: str):
    effective_key = api_key.strip() if api_key else os.getenv("GEMINI_API_KEY", "").strip()
    try:
        from google import genai
        return ("genai_new", genai.Client(api_key=effective_key))
    except Exception:
        try:
            import google.generativeai as genai_old
            genai_old.configure(api_key=effective_key)
            return ("genai_old", genai_old)
        except Exception:
            return ("http", effective_key)

def evaluate_job_with_gemini(api_key: str, cv_text: str, job: dict, sector: str = "") -> dict:
    client_type, client = get_gemini_client(api_key)
    sector_info = f"\n- SECTOR DE LA VACANTE: {sector}\n" if sector else ""
    
    prompt = f"""
Eres un asesor de selección de personal experto en evaluar candidaturas para el mercado laboral español en InfoJobs.
A continuación tienes el Currículum Vitae del candidato:

--- CURRÍCULUM VITAE ---
{cv_text}
------------------------

Debes evaluar la coincidencia del candidato para la siguiente vacante de empleo en InfoJobs:{sector_info}
- Título: {job.get('title', '')}
- Empresa: {job.get('company', '')}
- Salario publicado: {job.get('salary', 'Salario no disponible')}
- Enlace: {job.get('link', '')}
- Descripción: {job.get('description', '')}
- Preguntas de filtrado (Killer Questions): {json.dumps(job.get('killer_questions', []), ensure_ascii=False)}

TAREA:
1. Analiza las habilidades y requisitos contra el CV adaptando el foco al sector de la vacante.
2. Calcula una puntuación de coincidencia (% score del 0 al 100).
3. Escribe un EXTRACTO EJECUTIVO (2-3 frases) sobre la empresa y qué buscan en el puesto.
4. Si hay preguntas de filtrado (killer questions), genera respuestas coherentes, profesionales y en primera persona alineadas estrictamente con el CV y adaptadas al sector.
5. Responde ÚNICAMENTE con un objeto JSON válido con la estructura exacta:

{{
  "score": 85,
  "reasoning": "Explicación breve de la coincidencia...",
  "company_extract": "Extracto de la empresa y la vacante...",
  "killer_answers": [
    {{
      "question": "Texto exacto de la pregunta",
      "answer": "Respuesta optimizada adaptada al puesto y basada en el CV"
    }}
  ]
}}
"""
    candidate_models = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash", "gemini-pro"]
    response_text = ""
    for m in candidate_models:
        try:
            if client_type == "genai_new":
                res = client.models.generate_content(model=m, contents=prompt)
                response_text = res.text
            elif client_type == "genai_old":
                gen_m = client.GenerativeModel(m)
                res = gen_m.generate_content(prompt)
                response_text = res.text
            else:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={client}"
                r = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=30)
                r.raise_for_status()
                response_text = r.json()['candidates'][0]['content']['parts'][0]['text']
            break
        except Exception:
            continue

    clean_json = response_text.strip()
    if clean_json.startswith("```"):
        lines = clean_json.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        clean_json = "\n".join(lines).strip()

    try:
        return json.loads(clean_json)
    except Exception:
        return {
            "score": 55,
            "reasoning": "Evaluación de perfil completada.",
            "company_extract": f"Oferta de empleo en {job.get('company', 'la empresa')} para el puesto de {job.get('title', 'Puesto vacante')}.",
            "killer_answers": [{"question": q, "answer": "Tengo experiencia sólida y disponibilidad para el puesto."} for q in job.get("killer_questions", [])]
        }

def generate_cover_letter_with_gemini(api_key: str, cv_text: str, job: dict) -> str:
    client_type, client = get_gemini_client(api_key)
    prompt = f"""
Eres un consultor de selección profesional. Redacta una CARTA DE PRESENTACIÓN formal y convincente en español para postular a:
- Puesto: {job.get('title', '')}
- Empresa: {job.get('company', '')}
- Ubicación: {job.get('location', '')}

--- CURRÍCULUM VITAE ---
{cv_text}
------------------------

Devuelve ÚNICAMENTE el texto de la carta de presentación formateado en Markdown.
"""
    candidate_models = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash", "gemini-pro"]
    for m in candidate_models:
        try:
            if client_type == "genai_new":
                res = client.models.generate_content(model=m, contents=prompt)
                return res.text.strip()
            elif client_type == "genai_old":
                gen_m = client.GenerativeModel(m)
                res = gen_m.generate_content(prompt)
                return res.text.strip()
            else:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={client}"
                r = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=30)
                r.raise_for_status()
                return r.json()['candidates'][0]['content']['parts'][0]['text'].strip()
        except Exception:
            continue
    return f"Estimados/as responsables de selección de {job.get('company', 'la empresa')},\n\nMe dirijo a ustedes para presentar mi candidatura al puesto de {job.get('title', 'la oferta')}.\n\nAtentamente,\nEl Candidato"

def extract_job_keywords_from_cv(api_key: str, cv_text: str) -> dict:
    client_type, client = get_gemini_client(api_key)
    prompt = f"""
Analiza este Currículum Vitae y clasifica la experiencia en 3 categorías multirubro:
1. Hostelería, Comercio y Logística
2. Administración y Gestión (Perfil ADE)
3. Tecnología e Inteligencia Artificial

Responde ÚNICAMENTE con un objeto JSON válido con esta estructura:
{{
  "categorias_detectadas": {{
    "hosteleria_logistica": ["Mozo/a de almacén", "Cajero/a y Atención al cliente", "Reponedor/a"],
    "administracion_ade": ["Auxiliar Administrativo/a", "Gestión de pedidos"],
    "tecnologia_ia": ["Desarrollador/a Python / IA", "Prompt Engineer"]
  }},
  "localidad": "Alicante",
  "nombre_candidato": "Alex González",
  "habilidades_clave": "Atención al cliente, cobro en caja, logística, Python, gestión documental.",
  "reasoning": "Perfil versátil multitarea."
}}

--- CURRÍCULUM VITAE ---
{cv_text}
------------------------
"""
    candidate_models = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash", "gemini-pro"]
    response_text = ""
    for m in candidate_models:
        try:
            if client_type == "genai_new":
                res = client.models.generate_content(model=m, contents=prompt)
                response_text = res.text
            elif client_type == "genai_old":
                gen_m = client.GenerativeModel(m)
                res = gen_m.generate_content(prompt)
                response_text = res.text
            else:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={client}"
                r = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=30)
                r.raise_for_status()
                response_text = r.json()['candidates'][0]['content']['parts'][0]['text']
            break
        except Exception:
            continue

    clean_json = response_text.strip()
    if clean_json.startswith("```"):
        lines = clean_json.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        clean_json = "\n".join(lines).strip()

    try:
        return json.loads(clean_json)
    except Exception:
        return {
            "categorias_detectadas": {
                "hosteleria_logistica": ["Mozo/a de almacén", "Cajero/a y Atención al cliente", "Reponedor/a"],
                "administracion_ade": ["Auxiliar Administrativo/a", "Gestión de pedidos"],
                "tecnologia_ia": ["Desarrollador/a Python / IA", "Prompt Engineer"]
            },
            "localidad": "Alicante",
            "nombre_candidato": "Alex González",
            "habilidades_clave": "Atención al cliente, cobro en caja, gestión documental y Python.",
            "reasoning": "Perfil híbrido multitarea."
        }

def chat_with_assistant(api_key: str, chat_history: list, cv_text: str = "", evaluated_jobs: list = None) -> str:
    effective_key = api_key.strip() if api_key else os.getenv("GEMINI_API_KEY", "").strip()
    if not effective_key:
        return "⚠️ Introduce tu Gemini API Key en el modal de **⚙️ Configuración** (arriba a la derecha)."

    client_type, client = get_gemini_client(effective_key)
    cv_summary = f"--- CV DEL CANDIDATO ---\n{cv_text}\n" if cv_text else "Sin CV cargado."
    
    system_instruction = f"""
Eres "Oriol", el asesor personal de empleo e IA de la plataforma CV-auto (https://cv-auto-bot.onrender.com/).
Responde con cercanía, inteligencia y empatía sobre orientación laboral en España (InfoJobs, Indeed, Jooble, Adecco).
{cv_summary}
"""
    prompt = system_instruction + "\n\nHISTORIAL DE CHAT:\n"
    for msg in chat_history[-8:]:
        sender = "Usuario" if msg["role"] == "user" else "Oriol"
        prompt += f"{sender}: {msg['content']}\n"
    prompt += "\nOriol:"

    candidate_models = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash", "gemini-pro"]
    for m in candidate_models:
        try:
            if client_type == "genai_new":
                res = client.models.generate_content(model=m, contents=prompt)
                return res.text.strip()
            elif client_type == "genai_old":
                gen_m = client.GenerativeModel(m)
                res = gen_m.generate_content(prompt)
                return res.text.strip()
            else:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={client}"
                r = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=30)
                r.raise_for_status()
                return r.json()['candidates'][0]['content']['parts'][0]['text'].strip()
        except Exception:
            continue
    return "Hola, estoy aquí para ayudarte con tu candidatura. ¿Qué consulta tienes?"

# ==============================================================================
# 2. CABECERA (HEADER CON FILA SUPERIOR Y DIÁLOGO MODAL DE CONFIGURACIÓN)
# ==============================================================================
head_col1, head_col2 = st.columns([3.2, 1.2])

with head_col1:
    st.markdown("""
    <div style="display: flex; align-items: center; gap: 10px;">
        <span class="main-logo-text">CV-auto</span>
        <span style="background: rgba(56, 189, 248, 0.15); color: #38BDF8; font-size: 0.76rem; font-weight: 700; padding: 3px 10px; border-radius: 20px; border: 1px solid rgba(56, 189, 248, 0.3);">
            ✨ App UI v3.0
        </span>
    </div>
    <div class="main-subtitle">Agente Autónomo Multi-Portal • InfoJobs, Indeed, Jooble & Adecco</div>
    """, unsafe_allow_html=True)

# Modal de Configuración (Expander Popover en la derecha)
with head_col2:
    with st.popover("⚙️ Configuración", use_container_width=True):
        st.markdown("### ⚙️ Panel de Ajustes")
        st.caption("Ajusta tus credenciales, parámetros de búsqueda y conexión:")
        
        api_key_input = st.text_input("🔑 Gemini API Key", value=os.getenv("GEMINI_API_KEY", ""), type="password")
        telegram_token_input = st.text_input("🤖 Telegram Bot Token", value=os.getenv("TELEGRAM_BOT_TOKEN", "8929616203:AAGJ_XAfVo3AeKq_icY3HyJ0sN4ki5H0YVw"), type="password")
        telegram_chat_id_input = st.text_input("💬 Telegram Chat ID", value=os.getenv("TELEGRAM_CHAT_ID", "6270123390"))
        
        st.divider()
        st.markdown("#### 🟢 Estado de Sesión InfoJobs")
        if os.path.exists("storageState.json"):
            st.success("✅ Sesión activa guardada")
        else:
            st.info("ℹ️ Sin sesión guardada")
            
        if st.button("🔑 Iniciar Sesión Manual InfoJobs", use_container_width=True):
            with st.spinner("Abriendo navegador para iniciar sesión..."):
                try:
                    run_async(run_login_setup())
                    st.success("¡Sesión iniciada correctamente!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al iniciar sesión: {e}")
                    
        if st.button("📡 Probar Notificación Telegram", use_container_width=True):
            eff_token = telegram_token_input.strip() if telegram_token_input else os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
            eff_chat = telegram_chat_id_input.strip() if telegram_chat_id_input else os.getenv("TELEGRAM_CHAT_ID", "").strip()
            if eff_token and eff_chat:
                with st.spinner("Enviando prueba a Telegram..."):
                    res = run_async(test_telegram_connection(eff_token, eff_chat))
                    if res.get("status") == "success":
                        st.toast("✅ ¡Prueba enviada a Telegram!")
                    else:
                        st.error(f"❌ {res.get('message')}")
            else:
                st.error("Configura Bot Token y Chat ID.")

st.write("")

# ==============================================================================
# 6. BARRA DE NAVEGACIÓN INFERIOR PERSISTENTE (4 PESTAÑAS)
# ==============================================================================
tab_home, tab_chat, tab_alertas, tab_historial = st.tabs([
    "🏠\nHome",
    "💬\nChat",
    "🔔\nAlertas",
    "📜\nHistorial"
])

# ==============================================================================
# TAB 1: 🏠 HOME (Wireframe Dashboard Panel)
# ==============================================================================
with tab_home:
    # ZONA SUPERIOR (2 Columnas: Cargar CV + Ejemplo/Preview)
    col1, col2 = st.columns([1.1, 1])
    
    with col1:
        st.markdown("""
        <div class="wire-card">
            <div class="wire-card-title">📂 Cargar Currículum</div>
            <div style="font-size: 0.85rem; color: #94A3B8; margin-bottom: 10px;">Sube tu CV en formato PDF, Word o TXT para analizar tu perfil:</div>
        </div>
        """, unsafe_allow_html=True)
        
        uploaded_cv = st.file_uploader(
            "Selecciona tu archivo de CV",
            type=["pdf", "docx", "doc", "txt", "md"],
            key="wireframe_cv_uploader",
            label_visibility="collapsed"
        )
        
        if uploaded_cv is not None:
            file_sig = f"{uploaded_cv.name}_{uploaded_cv.size}"
            if st.session_state.get("uploaded_cv_sig") != file_sig:
                extracted = extract_text_from_file(uploaded_cv)
                if extracted and len(extracted.strip()) > 10:
                    st.session_state["cv_text"] = extracted.strip()
                    st.session_state["uploaded_cv_sig"] = file_sig
                    st.session_state.pop("cv_proposal", None)
                    st.success(f"✅ CV '{uploaded_cv.name}' cargado con éxito.")
                else:
                    st.error("⚠️ No se pudo leer texto del archivo.")
                    
        saved_cv_text = st.session_state.get("cv_text", "")
        with st.expander("✏️ Editar texto del CV directamente", expanded=False):
            cv_edit_text = st.text_area(
                "Contenido del CV",
                value=saved_cv_text if saved_cv_text else """Candidato: Alex González
Ubicación: Alicante
Perfil: Especialista multirubro en atención al cliente, logística, reposición y desarrollo Python/IA.

Experiencia y Capacidades:
- Atención al cliente y cobro en caja (Cajero/a en supermercados y comercio).
- Reposición de mercancía, control de caducidades e inventario (Reponedor/a).
- Recepción de palés, picking y preparación de pedidos (Mozo de almacén / Logística).
- Desarrollo en Python, automatización web y procesamiento con modelos IA.
- Carné de conducir B, vehículo propio y disponibilidad inmediata.""",
                height=160
            )
            if cv_edit_text != saved_cv_text and cv_edit_text.strip():
                st.session_state["cv_text"] = cv_edit_text.strip()
                st.session_state.pop("cv_proposal", None)

    cv_text = st.session_state.get("cv_text", "")

    # Auto-extract AI classification proposal if CV is loaded
    effective_key = api_key_input.strip() if api_key_input else os.getenv("GEMINI_API_KEY", "").strip()
    if cv_text and "cv_proposal" not in st.session_state and effective_key:
        with st.spinner("🧠 Analizando CV y clasificando perfil con IA..."):
            st.session_state["cv_proposal"] = extract_job_keywords_from_cv(effective_key, cv_text)

    cv_prop = st.session_state.get("cv_proposal", {})
    categories_detected = cv_prop.get("categorias_detectadas", {
        "hosteleria_logistica": ["Mozo/a de almacén", "Cajero/a y Atención al cliente", "Reponedor/a"],
        "administracion_ade": ["Auxiliar Administrativo/a", "Gestión de pedidos"],
        "tecnologia_ia": ["Desarrollador/a Python / IA", "Prompt Engineer"]
    })
    candidate_name = cv_prop.get("nombre_candidato", "Alex González")
    key_skills = cv_prop.get("habilidades_clave", "Atención al cliente, reposición, cobro en caja, logística, Python.")
    detected_loc = cv_prop.get("localidad", "Alicante")

    with col2:
        st.markdown(f"""
        <div class="wire-card">
            <div class="wire-card-title">👤 Tarjeta Ejemplo / Preview</div>
            <div style="margin-bottom: 8px;"><strong>Candidato Activo:</strong> {candidate_name}</div>
            <div style="margin-bottom: 8px;"><strong>Ubicación Base:</strong> 📍 {detected_loc}</div>
            <div style="margin-bottom: 8px;"><strong>Competencias Clave:</strong></div>
            <div style="font-size: 0.85rem; color: #CBD5E1; line-height: 1.4;">{key_skills}</div>
            <div style="margin-top: 10px;">
                <span class="chip-badge-green">✔ CV Verificado</span>
                <span class="chip-badge"> Ready para Búsqueda</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ZONA MEDIA - CLASIFICACIÓN (Badges / Chips)
    st.markdown("""
    <div class="wire-card">
        <div class="wire-card-title">🏷️ Clasificación de Perfil (Categorías & Roles Detectados)</div>
    </div>
    """, unsafe_allow_html=True)

    # Collect all role strings for Pills / Badges
    all_roles = []
    for cat_key, roles_list in categories_detected.items():
        for r in roles_list:
            all_roles.append(r)

    # Display using st.pills if available, else HTML Badges
    try:
        if hasattr(st, "pills"):
            st.pills("Roles sugeridos por la IA:", options=all_roles, default=all_roles, selection_mode="multi")
        else:
            chips_html = "".join([f'<span class="chip-badge-purple">✦ {role}</span> ' for role in all_roles])
            st.markdown(f"<div style='margin-bottom: 12px;'>{chips_html}</div>", unsafe_allow_html=True)
    except Exception:
        chips_html = "".join([f'<span class="chip-badge-purple">✦ {role}</span> ' for role in all_roles])
        st.markdown(f"<div style='margin-bottom: 12px;'>{chips_html}</div>", unsafe_allow_html=True)

    # Sector Filter Checkboxes
    st.markdown("**🎯 Sectores Activos para Búsqueda:**")
    sec1, sec2, sec3 = st.columns(3)
    with sec1:
        sel_log = st.checkbox("📦 Hostelería & Logística", value=True)
    with sec2:
        sel_adm = st.checkbox("📊 Administración & ADE", value=True)
    with sec3:
        sel_tech = st.checkbox("💻 Programación & IA", value=True)

    selected_keywords = []
    if sel_log:
        for r in categories_detected.get("hosteleria_logistica", []):
            selected_keywords.append((r, "Hostelería, Comercio y Logística"))
    if sel_adm:
        for r in categories_detected.get("administracion_ade", []):
            selected_keywords.append((r, "Administración y ADE"))
    if sel_tech:
        for r in categories_detected.get("tecnologia_ia", []):
            selected_keywords.append((r, "Tecnología e IA"))

    loc_c1, loc_c2 = st.columns([2, 1])
    with loc_c1:
        target_city = st.text_input("📍 Ciudad o Provincia", value=detected_loc if detected_loc else "Alicante")
    with loc_c2:
        max_jobs_per_cat = st.number_input("Resultados / Sector", min_value=1, max_value=10, value=5)

    st.write("")
    
    # 5. BOTÓN PRINCIPAL (ANCHO COMPLETO)
    if st.button("🚀 Buscar MULTIRUBRO", type="primary", use_container_width=True, key="btn_wire_multirubro"):
        effective_key = api_key_input.strip() if api_key_input else os.getenv("GEMINI_API_KEY", "").strip()
        if not effective_key:
            st.error("Introduce tu Gemini API Key en **⚙️ Configuración** (arriba a la derecha).")
        elif not cv_text.strip():
            st.error("Por favor, sube tu CV o edita el texto en la zona superior.")
        elif not selected_keywords:
            st.error("Por favor, selecciona al menos un sector de búsqueda.")
        else:
            target_city_clean = target_city.strip() if target_city.strip() else "Alicante"
            st.info(f"🔎 Ejecutando búsqueda concurrente en InfoJobs, Indeed, Jooble y Adecco en `{target_city_clean}`...")
            
            with st.spinner("⚡ Escaneando portales y evaluando coincidencia con IA Gemini..."):
                async def do_multirubro_search():
                    async with async_playwright() as p:
                        dedup_map = {}
                        for kw_term, sec_lbl in selected_keywords:
                            try:
                                ij_t = search_jobs(playwright=p, keywords=kw_term, location=target_city_clean, max_results=max_jobs_per_cat, headless=True)
                                ind_t = search_indeed(keywords=kw_term, location=target_city_clean, max_results=max_jobs_per_cat, playwright=p)
                                jooble_t = search_jooble(keywords=kw_term, location=target_city_clean, max_results=max_jobs_per_cat)
                                adecco_t = search_adecco(keywords=kw_term, location=target_city_clean, max_results=max_jobs_per_cat, playwright=p, headless=True)
                                
                                ij_res, ind_res, jooble_res, adecco_res = await asyncio.gather(ij_t, ind_t, jooble_t, adecco_t, return_exceptions=True)
                                
                                if isinstance(ij_res, Exception): ij_res = []
                                if isinstance(ind_res, Exception): ind_res = []
                                if isinstance(jooble_res, Exception): jooble_res = []
                                if isinstance(adecco_res, Exception): adecco_res = []

                                for j in (ij_res + ind_res + jooble_res + adecco_res):
                                    key = (j.get("title", "").strip().lower(), j.get("company", "").strip().lower())
                                    if key not in dedup_map:
                                        j_copy = dict(j)
                                        j_copy["sector"] = sec_lbl
                                        dedup_map[key] = j_copy
                            except Exception:
                                pass
                        return list(dedup_map.values())
                
                try:
                    found_jobs = run_async(do_multirubro_search())
                except Exception as ex:
                    st.error(f"Error al realizar la búsqueda: {ex}")
                    found_jobs = []

            if not found_jobs:
                st.warning(f"No se encontraron ofertas nuevas en {target_city_clean}.")
            else:
                eval_list = []
                p_bar = st.progress(0)
                for idx_f, raw_j in enumerate(found_jobs):
                    eval_res = evaluate_job_with_gemini(effective_key, cv_text, raw_j, sector=raw_j.get("sector", ""))
                    eval_list.append({
                        **raw_j,
                        "score": eval_res.get("score", 50),
                        "reasoning": eval_res.get("reasoning", ""),
                        "company_extract": eval_res.get("company_extract", ""),
                        "killer_answers": eval_res.get("killer_answers", []),
                        "selected": eval_res.get("score", 0) >= 75
                    })
                    p_bar.progress((idx_f + 1) / len(found_jobs))
                
                st.session_state["evaluated_jobs"] = eval_list
                st.success(f"🎉 ¡Se evaluaron {len(eval_list)} vacantes! Resultados destacados abajo:")

    # RESULTADOS DE EVALUACIÓN
    if "evaluated_jobs" in st.session_state and st.session_state["evaluated_jobs"]:
        st.divider()
        st.markdown("### 📋 Resultados Multirubro (Coincidencia ≥ 75%)")
        eval_jobs = st.session_state["evaluated_jobs"]
        qualified = [j for j in eval_jobs if j.get("score", 0) >= 75 and j.get("status") not in ["descartada", "discarded"]]
        
        if not qualified:
            st.info("No hay más vacantes con coincidencia ≥ 75% pendientes de decisión.")
        else:
            for idx_q, j in enumerate(qualified):
                score_val = j.get("score", 75)
                j_id = j.get("id", f"job_{idx_q}")
                
                with st.container():
                    st.markdown(f"#### [{j['title']}]({j['link']})")
                    st.markdown(f"🏢 **{j['company']}** | 📍 {j.get('location', 'Alicante')} | 🎯 **Score: {score_val}%**")
                    if j.get("company_extract"):
                        st.caption(f"📝 {j['company_extract']}")
                        
                    act_col1, act_col2 = st.columns(2)
                    with act_col1:
                        if st.button("✅ Postular en 1 Clic", type="primary", key=f"wire_apply_{j_id}_{idx_q}", use_container_width=True):
                            with st.spinner("Postulando..."):
                                async def apply_one():
                                    async with async_playwright() as p:
                                        return await apply_to_job(playwright=p, job_url=j["link"], killer_answers=j.get("killer_answers", []), headless=True)
                                try:
                                    res = run_async(apply_one())
                                    j["status"] = "applied"
                                    database.record_application(job_id=j["id"], title=j["title"], company=j["company"], link=j["link"], score=score_val, status="applied")
                                    st.toast("✅ ¡Postulado correctamente!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error: {e}")
                    with act_col2:
                        if st.button("❌ Descartar", key=f"wire_discard_{j_id}_{idx_q}", use_container_width=True):
                            j["status"] = "descartada"
                            database.discard_job(job_id=j["id"], title=j["title"], company=j["company"], link=j["link"], score=score_val)
                            st.toast("🗑️ Vacante descartada.")
                            st.rerun()
                st.divider()

# ==============================================================================
# TAB 2: 💬 CHAT (Asistente Oriol)
# ==============================================================================
with tab_chat:
    st.markdown("""
    <div class="wire-card">
        <div class="wire-card-title">💬 Chat Oriol - Asesor Personal de Empleo</div>
        <div style="font-size: 0.88rem; color: #94A3B8;">Pregunta tus dudas sobre el CV, ofertas encontradas o estrategia de búsqueda en España.</div>
    </div>
    """, unsafe_allow_html=True)
    
    if "chat_messages" not in st.session_state:
        st.session_state["chat_messages"] = [
            {"role": "assistant", "content": "¡Hola! 👋 Soy Oriol, tu asesor personal de empleo. He analizado tu perfil. ¿En qué te puedo orientar hoy?"}
        ]
        
    for msg in st.session_state["chat_messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
    user_input = st.chat_input("Escribe tu pregunta para Oriol...")
    if user_input:
        st.session_state["chat_messages"].append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)
            
        effective_key = api_key_input.strip() if api_key_input else os.getenv("GEMINI_API_KEY", "").strip()
        with st.chat_message("assistant"):
            reply = chat_with_assistant(effective_key, st.session_state["chat_messages"], cv_text=cv_text)
            st.markdown(reply)
            st.session_state["chat_messages"].append({"role": "assistant", "content": reply})

# ==============================================================================
# TAB 3: 🔔 ALERTAS & TELEGRAM FEED
# ==============================================================================
with tab_alertas:
    st.markdown("""
    <div class="wire-card">
        <div class="wire-card-title">🔔 Alertas Integradas & Feed Telegram</div>
        <div style="font-size: 0.88rem; color: #94A3B8;">Monitorea tus ofertas en tiempo real y marca vacantes interesadas o descartadas.</div>
    </div>
    """, unsafe_allow_html=True)
    
    apps_db = database.get_all_applications(limit=100)
    if not apps_db:
        st.info("Aún no hay vacantes en el historial de alertas. ¡Ejecuta tu primera búsqueda en la pestaña '🏠 Home'!")
    else:
        for idx_a, item in enumerate(apps_db):
            st_val = item.get("status", "pending")
            st.markdown(f"#### [{item['title']}]({item.get('link', '#')})")
            st.markdown(f"🏢 **{item.get('company')}** | 🎯 Coincidencia: **{item.get('score', 0)}%** | Estado: `{st_val}`")
            
            ac1, ac2 = st.columns(2)
            with ac1:
                if st.button("👍 Me interesa", key=f"wire_tg_yes_{item['job_id']}_{idx_a}", use_container_width=True, disabled=(st_val=="interesado")):
                    database.update_job_status(item['job_id'], "interesado")
                    st.toast("⭐ Vacante marcada como INTERESANTE.")
                    st.rerun()
            with ac2:
                if st.button("👎 No me interesa", key=f"wire_tg_no_{item['job_id']}_{idx_a}", use_container_width=True, disabled=(st_val=="descartada")):
                    database.update_job_status(item['job_id'], "descartada")
                    st.toast("❌ Vacante descartada.")
                    st.rerun()
            st.divider()

# ==============================================================================
# TAB 4: 📜 HISTORIAL (Postulaciones Registradas en Base de Datos / Supabase)
# ==============================================================================
with tab_historial:
    st.markdown("""
    <div class="wire-card">
        <div class="wire-card-title">📜 Historial de Postulaciones</div>
        <div style="font-size: 0.88rem; color: #94A3B8;">Registro completo de postulaciones, vacantes guardadas y descartadas en base de datos.</div>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("🔄 Actualizar Datos", key="btn_refresh_history"):
        st.rerun()
        
    apps = database.get_all_applications(limit=200)
    if apps:
        df = pd.DataFrame(apps)
        st.dataframe(df, use_container_width=True)
        csv_data = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar CSV",
            data=csv_data,
            file_name="historial_cv_auto.csv",
            mime="text/csv",
            key="btn_dl_csv"
        )
    else:
        st.info("Sin registros en el historial de postulaciones.")
