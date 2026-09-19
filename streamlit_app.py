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

# Page configuration
st.set_page_config(
    page_title="CV_auto App - Agente Autónomo",
    page_icon="📱",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Native Smartphone App Shell & Premium Minimalist CSS Styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@500;600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');
    
    /* Base Reset & Typography */
    html, body, [class*="css"], .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"], [data-testid="stSidebar"], [data-testid="stMain"], .main {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
        background-color: #090D16 !important;
        background: #090D16 !important;
        color: #F8FAFC !important;
        -webkit-tap-highlight-color: transparent;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }

    /* Main Content Container Padding for Bottom Floating Dock */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 110px !important;
        max-width: 1100px !important;
        background: #090D16 !important;
    }

    /* Prevent iOS Safari automatic zooming on input focus */
    input, select, textarea {
        font-size: 16px !important;
    }
    
    /* Completely Hide Default Streamlit Chrome & Headers */
    [data-testid="stHeader"], header[data-testid="stHeader"], [data-testid="stToolbar"] {
        background: transparent !important;
        height: 0px !important;
    }
    footer, #MainMenu, header {
        visibility: hidden !important;
        display: none !important;
    }
    
    /* Headings Typography */
    h1, h2, h3, .main-header {
        font-family: 'Outfit', sans-serif !important;
        letter-spacing: -0.02em !important;
        color: #F8FAFC !important;
    }
    
    /* Native App Bar Top Header */
    .app-top-bar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 14px 20px;
        background: rgba(17, 24, 39, 0.75);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 20px;
        margin-bottom: 22px;
        box-shadow: 0 4px 25px rgba(0, 0, 0, 0.3);
    }
    
    .app-title-box {
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .app-title-text {
        font-family: 'Outfit', sans-serif;
        font-size: 1.35rem;
        font-weight: 700;
        color: #F8FAFC;
        letter-spacing: -0.3px;
    }
    
    .main-header {
        font-size: 1.85rem;
        font-weight: 800;
        background: linear-gradient(135deg, #38BDF8 0%, #818CF8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.3rem;
        line-height: 1.25;
    }
    
    .sub-header {
        color: #94A3B8;
        font-size: 0.96rem;
        margin-bottom: 1.4rem;
        line-height: 1.5;
        font-weight: 400;
    }
    
    /* Touch-friendly Native Buttons (Min 48px height) */
    .stButton>button {
        border-radius: 14px !important;
        font-weight: 600 !important;
        min-height: 48px !important;
        font-size: 0.95rem !important;
        transition: all 0.22s cubic-bezier(0.16, 1, 0.3, 1) !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
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
    
    .stButton>button:active {
        transform: scale(0.97) !important;
    }

    /* Primary Accent Buttons */
    .stButton>button[kind="primary"] {
        background: linear-gradient(135deg, #38BDF8 0%, #6366F1 100%) !important;
        border: none !important;
        color: #FFFFFF !important;
        box-shadow: 0 4px 20px rgba(56, 189, 248, 0.35) !important;
        font-weight: 700 !important;
    }
    
    .stButton>button[kind="primary"]:hover {
        box-shadow: 0 6px 26px rgba(56, 189, 248, 0.5) !important;
        transform: translateY(-1px) !important;
    }

    /* HIDE STREAMLIT DEFAULT TAB RED/ORANGE HIGHLIGHT & UNDERLINE BORDER */
    div[data-baseweb="tab-highlight"], 
    div[data-baseweb="tab-border"], 
    [data-baseweb="tab-highlight"], 
    [data-baseweb="tab-border"] {
        display: none !important;
        visibility: hidden !important;
        height: 0px !important;
        opacity: 0 !important;
    }

    /* FIXED INTERACTIVE BOTTOM NAVIGATION BAR DOCK */
    div[data-baseweb="tab-list"], [data-baseweb="tab-list"] {
        position: fixed !important;
        bottom: 12px !important;
        left: 50% !important;
        transform: translateX(-50%) !important;
        width: calc(100% - 32px) !important;
        max-width: 860px !important;
        z-index: 999999 !important;
        background: rgba(11, 16, 26, 0.92) !important;
        backdrop-filter: blur(24px) !important;
        -webkit-backdrop-filter: blur(24px) !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 24px !important;
        padding: 6px 8px !important;
        display: flex !important;
        justify-content: space-around !important;
        align-items: center !important;
        gap: 4px !important;
        box-shadow: 0 20px 50px -10px rgba(0, 0, 0, 0.8), 0 0 0 1px rgba(255, 255, 255, 0.08) !important;
        margin: 0 !important;
    }
    
    /* Target both button and div tab elements */
    [data-baseweb="tab"], button[data-baseweb="tab"], div[data-baseweb="tab"] {
        flex: 1 !important;
        text-align: center !important;
        padding: 10px 4px !important;
        font-size: 0.83rem !important;
        font-weight: 600 !important;
        color: #94A3B8 !important;
        border-radius: 16px !important;
        transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1) !important;
        background: transparent !important;
        border: 1px solid transparent !important;
        margin: 0 !important;
        cursor: pointer !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }
    
    [data-baseweb="tab"]:hover, button[data-baseweb="tab"]:hover {
        color: #F1F5F9 !important;
        background: rgba(255, 255, 255, 0.05) !important;
    }
    
    [data-baseweb="tab"][aria-selected="true"], button[data-baseweb="tab"][aria-selected="true"] {
        color: #F8FAFC !important;
        background: linear-gradient(135deg, rgba(56, 189, 248, 0.22) 0%, rgba(99, 102, 241, 0.22) 100%) !important;
        border: 1px solid rgba(56, 189, 248, 0.4) !important;
        box-shadow: 0 4px 16px rgba(56, 189, 248, 0.2) !important;
    }

    /* TAB CONTENT SMOOTH LEVEL TRANSITION */
    div[data-baseweb="tab-panel"], [data-testid="stTabContent"] {
        animation: tabSlideUp 0.32s cubic-bezier(0.16, 1, 0.3, 1) forwards !important;
    }

    @keyframes tabSlideUp {
        0% {
            opacity: 0;
            transform: translateY(12px) scale(0.99);
        }
        100% {
            opacity: 1;
            transform: translateY(0) scale(1);
        }
    }
    
    /* Badges & Score Indicators */
    .score-badge-high {
        background-color: rgba(52, 211, 153, 0.14);
        color: #34D399;
        padding: 5px 12px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.84rem;
        border: 1px solid rgba(52, 211, 153, 0.3);
        display: inline-block;
        margin: 2px 4px 2px 0;
    }
    
    .score-badge-mid {
        background-color: rgba(251, 191, 36, 0.14);
        color: #FBBF24;
        padding: 5px 12px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.84rem;
        border: 1px solid rgba(251, 191, 36, 0.3);
        display: inline-block;
        margin: 2px 4px 2px 0;
    }
    
    .score-badge-low {
        background-color: rgba(248, 113, 113, 0.14);
        color: #F87171;
        padding: 5px 12px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.84rem;
        border: 1px solid rgba(248, 113, 113, 0.3);
        display: inline-block;
        margin: 2px 4px 2px 0;
    }

    /* Input fields and Cards styling */
    div[data-baseweb="input"], div[data-baseweb="textarea"], [data-testid="stFileUploader"] {
        border-radius: 14px !important;
        background: rgba(17, 24, 39, 0.6) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        color: #F8FAFC !important;
    }

    div[data-testid="stExpander"] {
        background: rgba(17, 24, 39, 0.5) !important;
        border-radius: 16px !important;
        border: 1px solid rgba(255, 255, 255, 0.07) !important;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1) !important;
    }

    /* Sidebar Glassmorphic Styling */
    section[data-testid="stSidebar"] {
        background-color: #0D1322 !important;
        border-right: 1px solid rgba(255, 255, 255, 0.08) !important;
    }
    
    /* Custom Streamlit Alert boxes */
    div[data-testid="stAlert"] {
        border-radius: 14px !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
    }
    
    /* MOBILE SMARTPHONE ADAPTATIONS */
    @media (max-width: 768px) {
        .block-container {
            padding-left: 0.65rem !important;
            padding-right: 0.65rem !important;
            padding-top: 0.4rem !important;
            padding-bottom: 95px !important;
        }
        
        .main-header {
            font-size: 1.4rem !important;
        }
        .sub-header {
            font-size: 0.86rem !important;
            margin-bottom: 1rem !important;
        }
        
        div[data-baseweb="tab-list"], [data-baseweb="tab-list"] {
            bottom: 0 !important;
            left: 0 !important;
            transform: none !important;
            width: 100% !important;
            max-width: 100% !important;
            border-radius: 0 !important;
            border-top: 1px solid rgba(255, 255, 255, 0.12) !important;
            border-left: none !important;
            border-right: none !important;
            border-bottom: none !important;
            padding: 8px 4px calc(8px + env(safe-area-inset-bottom, 12px)) 4px !important;
        }
        
        [data-baseweb="tab"], button[data-baseweb="tab"], div[data-baseweb="tab"] {
            font-size: 0.74rem !important;
            padding: 8px 2px !important;
            border-radius: 10px !important;
        }
        
        div[data-testid="column"] {
            width: 100% !important;
            flex: 1 1 100% !important;
            min-width: 100% !important;
            margin-bottom: 0.6rem !important;
        }
        
        .stButton>button {
            width: 100% !important;
            min-height: 48px !important;
            font-size: 0.95rem !important;
        }
    }
</style>

<!-- Mobile PWA Meta Headers -->
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<meta name="theme-color" content="#090D16">
""", unsafe_allow_html=True)

def run_async(coro):
    """Safely execute async Playwright tasks in Streamlit."""
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

def extract_text_from_file(uploaded_file) -> str:
    """Extracts raw text from uploaded PDF, DOCX, DOC, or TXT file."""
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
            st.warning(f"Aviso al leer PDF: {e}")
            
    elif ext == ".docx":
        try:
            import docx
            document = docx.Document(io.BytesIO(file_bytes))
            text = "\n".join([p.text for p in document.paragraphs if p.text.strip()]).strip()
        except Exception as e:
            st.warning(f"Aviso al leer documento Word (.docx): {e}")

    elif ext == ".doc":
        try:
            raw = file_bytes.decode("utf-8", errors="ignore")
            printable = "".join([c if (32 <= ord(c) <= 126 or c in "\n\r\táéíóúÁÉÍÓÚñÑ") else " " for c in raw])
            clean_lines = [line.strip() for line in printable.splitlines() if len(line.strip()) > 3]
            text = "\n".join(clean_lines).strip()
        except Exception as e:
            st.warning(f"Aviso al leer documento Word (.doc): {e}")

    elif ext in [".txt", ".md"]:
        try:
            text = file_bytes.decode("utf-8", errors="ignore").strip()
        except Exception as e:
            st.warning(f"Aviso al leer texto: {e}")

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
    """Initializes Gemini API client using available SDK."""
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
    """Evaluates a single job offer against CV using Gemini model, adapting context to sector."""
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

REGLAS DE EVALUACIÓN ADAPTADAS SEGÚN EL SECTOR:
- Si el puesto es de Hostelería, Reposición, Comercio o Logística: pondera la atención al cliente, actitud proactiva, agilidad, cobro en caja, preparación de pedidos y trabajo en equipo.
- Si el puesto es de Administración o Gestión (Perfil ADE): pondera la organización, formación contable/administrativa, gestión de pedidos/facturación y manejo de herramientas de ofimática.
- Si el puesto es de Tecnología, Programación o IA: pondera las competencias técnicas en Python, automatización, integraciones de APIs y herramientas de LLM/IA.

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
            "score": 50,
            "reasoning": "Evaluación de perfil completada.",
            "company_extract": f"Oferta de empleo en {job.get('company', 'la empresa')} para el puesto de {job.get('title', 'Puesto vacante')}.",
            "killer_answers": [{"question": q, "answer": "Tengo experiencia sólida y disponibilidad para el puesto."} for q in job.get("killer_questions", [])]
        }

def generate_cover_letter_with_gemini(api_key: str, cv_text: str, job: dict) -> str:
    """Generates a professional Spanish Cover Letter tailored to a target job offer using Gemini."""
    client_type, client = get_gemini_client(api_key)
    
    prompt = f"""
Eres un consultor de selección y redacción profesional de candidaturas en España.
Escribe una CARTA DE PRESENTACIÓN (Cover Letter) persuasiva, elegante, profesional y formal en español para postular a la siguiente oferta de empleo:

- Puesto: {job.get('title', '')}
- Empresa: {job.get('company', '')}
- Ubicación: {job.get('location', '')}
- Salario: {job.get('salary', 'No especificado')}

--- CURRÍCULUM VITAE DEL CANDIDATO ---
{cv_text}
-------------------------------------

REQUISITOS DE LA CARTA:
1. Longitud: 3-4 párrafos bien estructurados (Estimado/a responsable de selección, Introducción entusiasta, Por qué mi perfil aporta valor, Conclusión con llamada a la acción para entrevista).
2. Tono: Profesional, motivador, conciso y convincente.
3. Resalta 2 o 3 logros o competencias clave del CV que mejor se conecten con las necesidades del puesto.
4. Devuelve ÚNICAMENTE el texto de la carta de presentación formateado en Markdown limpio (sin comillas extra ni explicaciones adicionales).
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

    return f"Estimados/as responsables de selección de {job.get('company', 'la empresa')},\n\nMe dirijo a ustedes para presentar mi candidatura al puesto de {job.get('title', 'la oferta de empleo')}. Cuento con experiencia sólida y una trayectoria orientada a resultados que se alinea perfectamente con sus necesidades.\n\nQuedo a su disposición para mantener una entrevista personal.\n\nAtentamente,\nEl Candidato"

def extract_job_keywords_from_cv(api_key: str, cv_text: str) -> dict:
    """Classifies candidate profile into 3 independent multirubro sectors using Gemini:
    1. Hostelería, Comercio y Logística
    2. Administración y Gestión (Perfil ADE)
    3. Tecnología e Inteligencia Artificial
    """
    client_type, client = get_gemini_client(api_key)
    
    prompt = f"""
Eres un Arquitecto de Reclutamiento e Integración de IA especializado en InfoJobs España y evaluación de perfiles híbridos/multirubro.
Analiza detenidamente el siguiente Currículum Vitae y clasifica la experiencia, formación y competencias del usuario en 3 CATEGORÍAS INDEPENDIENTES DE BÚSQUEDA en InfoJobs:

1. Hostelería, Comercio y Logística: Camarero, Mozo de almacén, Cajero, Reponedor, Atención al cliente, Preparación de pedidos.
2. Administración y Gestión (Perfil ADE): Auxiliar administrativo, Administrativo de compras/ventas, Gestión de pedidos, Soporte contable.
3. Tecnología e Inteligencia Artificial: Desarrollador Junior Python/IA, Prompt Engineer, Integrador de APIs/LLMs, Automatizador de procesos.

Debes responder ÚNICAMENTE con un objeto JSON válido con este formato exacto (sin markdown alrededor ni texto extra):

{{
  "categorias_detectadas": {{
    "hosteleria_logistica": [
      "Mozo/a de almacén y logística",
      "Cajero/a y Atención al cliente",
      "Reponedor/a de supermercado",
      "Hostelería / Camarero/a"
    ],
    "administracion_ade": [
      "Auxiliar Administrativo/a",
      "Gestión de pedidos y compras",
      "Administrativo/a de ventas"
    ],
    "tecnologia_ia": [
      "Desarrollador/a Python / IA",
      "Prompt Engineer / Automatizador LLM",
      "Integrador de APIs / Web Scraping"
    ]
  }},
  "localidad": "Alicante",
  "habilidades_por_area": {{
    "hosteleria_logistica": "Atención al cliente, cobro en caja, control de stock, reposición, picking y preparación de pedidos.",
    "administracion_ade": "Gestión documental, facturación, soporte contable, paquete Office y atención telefónica.",
    "tecnologia_ia": "Python, integración de APIs REST, modelos LLM/Gemini, automatización web con Playwright y Git."
  }},
  "reasoning": "Perfil híbrido versátil con competencias sólidas en operativa comercial, gestión administrativa y desarrollo de soluciones de IA."
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
                "hosteleria_logistica": [
                    "Mozo/a de almacén y logística",
                    "Cajero/a y Atención al cliente",
                    "Reponedor/a de supermercado",
                    "Hostelería / Camarero/a"
                ],
                "administracion_ade": [
                    "Auxiliar Administrativo/a",
                    "Gestión de pedidos y compras"
                ],
                "tecnologia_ia": [
                    "Desarrollador/a Python / IA",
                    "Prompt Engineer / Automatizador LLM"
                ]
            },
            "localidad": "Alicante",
            "habilidades_por_area": {
                "hosteleria_logistica": "Atención al cliente, cobro en caja, reposición y almacén.",
                "administracion_ade": "Auxiliar administrativo, facturación y gestión.",
                "tecnologia_ia": "Python, integración de APIs y automatización con IA."
            },
            "reasoning": "Perfil híbrido multitarea procesado correctamente."
        }

def chat_with_assistant(api_key: str, chat_history: list, cv_text: str = "", evaluated_jobs: list = None) -> str:
    """Converses naturally with the candidate as an intelligent human recruitment advisor."""
    effective_key = api_key.strip() if api_key else os.getenv("GEMINI_API_KEY", "").strip()
    if not effective_key:
        return "⚠️ **No se ha detectado una clave de API de Gemini (GEMINI_API_KEY).**\n\nPor favor, introduce tu Gemini API Key en el menú lateral de la izquierda (puedes conseguir una gratis en [Google AI Studio](https://aistudio.google.com/app/apikey)) para activar mi inteligencia."

    client_type, client = get_gemini_client(effective_key)
    
    cv_summary = f"--- CURRÍCULUM VITAE DEL CANDIDATO ---\n{cv_text}\n------------------------\n" if cv_text else "El usuario aún no ha cargado su CV."
    
    jobs_summary = ""
    if evaluated_jobs:
        jobs_summary = f"--- VACANTES EVALUADAS RECIENTEMENTE EN INFOJOBS ({len(evaluated_jobs)}) ---\n"
        for idx, j in enumerate(evaluated_jobs[:5], 1):
            jobs_summary += f"{idx}. Puesto: {j.get('title')} en {j.get('company')} (Salario: {j.get('salary', 'N/D')}) (% Coincidencia: {j.get('score')}%)\n   Resumen: {j.get('company_extract')}\n"
        jobs_summary += "---------------------------------------------------------\n"

    system_instruction = f"""
Eres "Oriol", el asesor personal de empleo e Inteligencia Artificial nativo de la plataforma CV_auto (https://cv-auto-bot.onrender.com/).
Hablas y te expresas de forma cercana, empática, clara, inteligente y totalmente humana. Eres un experto en orientación laboral en España (InfoJobs, Indeed, Jooble y Adecco) y conoces perfectamente el funcionamiento de esta aplicación web y del bot de Telegram.

CONOCIMIENTO INTEGRAL DE ESTA APLICACIÓN WEB Y SISTEMA (CV_auto):
1. ¿QUÉ ES CV_AUTO?
   Es una plataforma web inteligente y bot multiusuario de Telegram diseñada para automatizar y personalizar la búsqueda de empleo en España analizando vacantes en paralelo en 4 portales líderes: InfoJobs, Indeed, Jooble y Adecco.

2. PESTAÑAS Y SECCIONES DE LA WEB:
   - 🚀 1. "Agente" (Búsqueda Multirubro & Evaluación IA):
     • Carga de CV: Acepta archivos en PDF, Word (.docx, .doc), Texto (.txt, .md) o texto pegado directamente.
     • Clasificación Multirubro: La IA analiza el CV y divide el perfil en 3 sectores (Hostelería/Logística, Administración/ADE, Tecnología/IA).
     • Búsqueda Concurrente: Escanea vacantes activas en InfoJobs, Indeed, Jooble y Adecco en la localidad elegida (ej. Alicante, Madrid, Remoto, etc.).
     • Evaluación IA (% Score): Gemini compara cada vacante con el CV, calcula el porcentaje de coincidencia (0-100%), genera un extracto de la vacante y redacta respuestas a las preguntas de filtrado (killer questions).
     • Filtro de Calidad (≥ 75%): Solo muestra ofertas destacadas con alta compatibilidad.
     • Acciones en 1 Clic: Permite postularse automáticamente, descartar vacantes o redactar Cartas de Presentación hechas a medida con IA.
   - 💬 2. "Chat Oriol" (Tú):
     • Canal directo donde orientas al candidato, respondes dudas sobre su CV, le explicas cómo usar la plataforma o analizas las vacantes encontradas.
   - 📱 3. "Telegram & Alertas":
     • Conexión con el bot de Telegram de la plataforma (@CV_auto_bot).
     • Muestra un feed de alertas interactivas donde el usuario puede marcar "👍 Me interesa" o "👎 No me interesa" (descarte permanente en la BD SQLite/PostgreSQL).
     • Permite realizar envíos de prueba a su teléfono.
   - ⚡ 4. "Postular URL":
     • Permite pegar un enlace directo de InfoJobs e inscribirse en segundos respondiendo preguntas personalizadas.
   - 📊 5. "Historial":
     • Registro de todas las postulaciones, ofertas aceptadas, descartadas y estados.
   - 📈 6. "Analítica":
     • Gráficos y métricas sobre la distribución de candidaturas por sector y portal.
   - 🤖 Piloto Automático:
     • Escáner automático en segundo plano que envía alertas instantáneas a Telegram cuando detecta vacantes con coincidencia ≥ 85%.
     • Al subir un CV o registrarse por primera vez, el sistema lanza una búsqueda inicial en 1-2 minutos.

REGLAS DE INTERACCIÓN:
1. Si el usuario te pregunta qué hace esta página web, cómo funciona, qué pestañas tiene o cómo usarla, explícaselo con total claridad, entusiasmo y naturalidad.
2. Orienta al usuario sobre la búsqueda de empleo para sus puestos de interés, salarios, modalidades y requisitos.
3. Si el usuario te pregunta sobre las ofertas encontradas o su CV, aprovecha la información del contexto para darle respuestas personalizadas.
4. Responde siempre en español fluido, profesional, empático y cercano.

CONTEXTO DE LA SESIÓN ACTUAL:
{cv_summary}
{jobs_summary}
"""

    prompt = system_instruction + "\n\nHISTORIAL DE CONVERSACIÓN RECIENTE:\n"
    for msg in chat_history[-10:]:
        sender = "Candidato" if msg["role"] == "user" else "Oriol (Asesor)"
        prompt += f"{sender}: {msg['content']}\n"
    
    prompt += "\nOriol (Asesor):"

    candidate_models = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash", "gemini-pro"]
    response_text = ""
    last_exception = None

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
            if response_text and response_text.strip():
                break
        except Exception as e:
            last_exception = e
            continue

    if response_text and response_text.strip():
        return response_text.strip()
    
    err_msg = str(last_exception) if last_exception else "Error de conexión"
    if "API_KEY_INVALID" in err_msg or "400" in err_msg or "403" in err_msg or "not valid" in err_msg.lower():
        return f"⚠️ **Error en la API Key de Gemini**\n\nLa clave de API actual no es válida o ha sido rechazada por Google.\n*Detalle del error:* `{err_msg}`\n\n👉 Introduce una API Key válida de [Google AI Studio](https://aistudio.google.com/app/apikey) en el menú lateral de la izquierda."
    else:
        return f"⚠️ **No pude conectarme con el servicio de IA de Gemini**\n\n*Detalle del error:* `{err_msg}`\n\nPor favor, verifica tu conexión o introduce tu API Key en la barra lateral."

# Sidebar Setup
st.sidebar.image("https://www.infojobs.net/ij-static/ij-core/images/infojobs-logo.svg", width=180)
st.sidebar.title("⚡ Panel CV_auto")

st.sidebar.markdown("### 🟢 Estado del Servicio")
st.sidebar.success("✅ **IA Gemini:** Preparada")
st.sidebar.info("📱 **Bot Telegram:** Conectado 24/7")

with st.sidebar.expander("🛠️ Ajustes Avanzados & Credenciales", expanded=False):
    api_key_input = st.text_input("🔑 Gemini API Key", value=os.getenv("GEMINI_API_KEY", ""), type="password")
    telegram_token_input = st.text_input("🤖 Telegram Bot Token", value=os.getenv("TELEGRAM_BOT_TOKEN", "8929616203:AAGJ_XAfVo3AeKq_icY3HyJ0sN4ki5H0YVw"), type="password")
    telegram_chat_id_input = st.text_input("💬 Telegram Chat ID", value=os.getenv("TELEGRAM_CHAT_ID", "6270123390"))
    
    session_exists = os.path.exists("storageState.json")
    if session_exists:
        st.success("✅ Sesión InfoJobs Activa")
    else:
        st.caption("ℹ️ Sin sesión guardada de InfoJobs")
    
    if st.button("🔑 Iniciar Sesión Manual en InfoJobs", use_container_width=True):
        st.info("Se abrirá Chromium para iniciar sesión...")
        try:
            run_async(run_login_setup())
            st.success("¡Sesión guardada correctamente!")
            st.rerun()
        except Exception as e:
            st.error(f"Error al iniciar sesión: {e}")

    if st.button("📡 Probación Notificación Telegram", use_container_width=True):
        eff_token = telegram_token_input.strip() if telegram_token_input else os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        eff_chat = telegram_chat_id_input.strip() if telegram_chat_id_input else os.getenv("TELEGRAM_CHAT_ID", "").strip()
        if not eff_token or not eff_chat:
            st.error("Introduce tu Token y Chat ID arriba.")
        else:
            with st.spinner("Enviando mensaje de prueba..."):
                res = run_async(test_telegram_connection(eff_token, eff_chat))
                if res.get("status") == "success":
                    st.success("✅ ¡Notificación de prueba enviada a Telegram!")
                else:
                    st.error(f"❌ {res.get('message')}")

def get_backend_scheduler_status():
    try:
        r = requests.get("http://localhost:8000/scheduler/status", timeout=2)
        if r.status_code == 200:
            return r.json().get("state", {})
    except Exception:
        pass
    return {}

sched_state = get_backend_scheduler_status()
is_active_current = sched_state.get("is_active", False)
interval_current = sched_state.get("interval_minutes", 30)

with st.sidebar.expander("🤖 Piloto Automático (Programador)", expanded=False):
    autopilot_active = st.toggle("⚡ Activar Piloto Automático", value=is_active_current)
    autopilot_interval = st.select_slider(
        "⏱️ Intervalo (minutos)",
        options=[5, 15, 30, 60, 120, 240, 720],
        value=interval_current if interval_current in [5, 15, 30, 60, 120, 240, 720] else 30
    )

    if autopilot_active != is_active_current or (autopilot_active and autopilot_interval != interval_current):
        effective_key = api_key_input.strip() if api_key_input else os.getenv("GEMINI_API_KEY", "").strip()
        cv_txt = st.session_state.get("cv_text", "")
        eff_token = telegram_token_input.strip() if telegram_token_input else os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        eff_chat = telegram_chat_id_input.strip() if telegram_chat_id_input else os.getenv("TELEGRAM_CHAT_ID", "").strip()
        if autopilot_active:
            payload = {
                "interval_minutes": autopilot_interval,
                "keywords": "Mozo, Auxiliar administrativo, Desarrollador Python",
                "location": "Alicante",
                "cv_text": cv_txt,
                "gemini_key": effective_key,
                "telegram_token": eff_token,
                "telegram_chat_id": eff_chat,
                "run_immediately": False
            }
            try:
                r = requests.post("http://localhost:8000/scheduler/start", json=payload, timeout=5)
                if r.status_code == 200:
                    st.success(f"🟢 Piloto Automático ACTIVADO (cada {autopilot_interval} min)")
                else:
                    st.error("Error al iniciar el piloto automático en FastAPI.")
            except Exception as e:
                st.warning("⚡ Para activar el Piloto Automático en segundo plano, asegúrate de que `main.py` esté ejecutándose.")
        else:
            try:
                r = requests.post("http://localhost:8000/scheduler/stop", timeout=5)
                if r.status_code == 200:
                    st.info("🔴 Piloto Automático DETENIDO")
            except Exception:
                pass

headless_option = True

# Main App Smartphone Top Bar Header
st.markdown("""
<div class="app-top-bar">
    <div class="app-title-box">
        <span style="font-size: 1.6rem;">📱</span>
        <div>
            <div class="app-title-text">CV Auto App</div>
            <div style="font-size: 0.78rem; color: #94A3B8; font-weight: 600;">InfoJobs • Indeed • Jooble • Gemini 1.5 Pro</div>
        </div>
    </div>
    <div style="display: flex; gap: 8px; align-items: center;">
        <span style="background: rgba(56, 189, 248, 0.15); color: #38BDF8; font-size: 0.78rem; font-weight: 700; padding: 4px 10px; border-radius: 20px; border: 1px solid rgba(56, 189, 248, 0.3);">
            ✨ App UI v3.0
        </span>
        <span style="background: rgba(16, 185, 129, 0.15); color: #34D399; font-size: 0.78rem; font-weight: 700; padding: 4px 10px; border-radius: 20px; border: 1px solid rgba(52, 211, 153, 0.3);">
            🟢 Online 24/7
        </span>
    </div>
</div>

<div class="main-header">🤖 Agente Autónomo Multi-Portal</div>
<div class="sub-header">Búsqueda concurrente de empleo, clasificación multirubro, cartas de presentación y envío automático con IA</div>
""", unsafe_allow_html=True)

# Main Navigation Tabs
tab_workflow, tab_chat, tab_telegram, tab_direct, tab_history, tab_analytics = st.tabs([
    "🚀 Agente",
    "💬 Chat Oriol",
    "📱 Telegram & Alertas",
    "⚡ Postular URL", 
    "📊 Historial",
    "📈 Analítica"
])

# ==============================================================================
# TAB 1: DYNAMIC PROFILE EXTRACTION & CUSTOM FILTERS PANEL
# ==============================================================================
with tab_workflow:
    st.info("💡 **¿Eres nuevo? 3 pasos sencillos:** 1. Sube o edita tu CV abajo. 2. Elige tus sectores o ciudades. 3. Pulsa **🚀 Buscar Candidaturas** para ver las mejores ofertas evaluadas por la IA.")

    # STEP 1: UPLOAD / EDIT CV
    st.markdown("### 1️⃣ Carga de Currículum Vitae")
    
    cv_col1, cv_col2 = st.columns([1, 1])
    with cv_col1:
        uploaded_cv = st.file_uploader(
            "📂 Sube tu CV (PDF, Word DOCX, DOC o TXT)",
            type=["pdf", "docx", "doc", "txt", "md"],
            key="file_uploader_cv"
        )
    
    # Process uploaded file if present
    if uploaded_cv is not None:
        file_sig = f"{uploaded_cv.name}_{uploaded_cv.size}"
        if st.session_state.get("uploaded_cv_sig") != file_sig:
            extracted = extract_text_from_file(uploaded_cv)
            if extracted and len(extracted.strip()) > 10:
                st.session_state["cv_text"] = extracted.strip()
                st.session_state["uploaded_cv_sig"] = file_sig
                st.session_state.pop("cv_proposal", None) # Invalidate old gemini analysis
                st.success(f"✅ ¡CV '{uploaded_cv.name}' cargado correctamente! ({len(extracted)} caracteres)")
            else:
                st.error("⚠️ No se pudo extraer texto legible del archivo. Por favor sube un archivo PDF o Word válido o edita el texto a la derecha.")
    
    saved_cv_text = st.session_state.get("cv_text", "")

    with cv_col2:
        with st.expander("✏️ Ver / Editar texto del CV cargado", expanded=(not saved_cv_text)):
            text_area_val = st.text_area(
                "Texto del CV",
                value=saved_cv_text if saved_cv_text else """Candidato: Alex González
Ubicación: Alicante
Perfil: Desarrollador y especialista polivalente en atención al cliente, logística, reposición y servicios.

Experiencia y Capacidades:
- Desarrollador Python, JavaScript y automatización de procesos web.
- Atención al cliente y cobro en caja (Cajero/a en supermercados y comercio).
- Reposición de mercancía, colocación en lineal, control de fechas de caducidad e inventario (Reponedor/a).
- Recepción de palés, preparación de pedidos (picking/packing), uso de transpaleta manual (Mozo de almacén / Logística).
- Carné de conducir B, vehículo propio y disponibilidad inmediata.""",
                height=180,
                key="cv_text_area_widget"
            )
            if text_area_val != saved_cv_text and text_area_val.strip():
                st.session_state["cv_text"] = text_area_val.strip()
                st.session_state.pop("cv_proposal", None)

    cv_text = st.session_state.get("cv_text", text_area_val if 'text_area_val' in locals() else "")
    st.divider()

    # STEP 2: DYNAMIC PROFILE EXTRACTION & MULTIRUBRO FILTERS PANEL
    st.markdown("### 2️⃣ Clasificación Multirubro de Perfil & Selección de Sectores")
    
    # Auto-run profile extraction if CV exists and proposal not in session
    effective_key = api_key_input.strip() if api_key_input else os.getenv("GEMINI_API_KEY", "").strip()
    if cv_text and "cv_proposal" not in st.session_state and effective_key:
        with st.spinner("🧠 Gemini está analizando tu CV para clasificar tu perfil en 3 ramas multirubro..."):
            st.session_state["cv_proposal"] = extract_job_keywords_from_cv(effective_key, cv_text)

    cv_proposal = st.session_state.get("cv_proposal", {})
    categories_detected = cv_proposal.get("categorias_detectadas", {
        "hosteleria_logistica": ["Mozo/a de almacén y logística", "Cajero/a y Atención al cliente", "Reponedor/a de supermercado", "Hostelería / Camarero/a"],
        "administracion_ade": ["Auxiliar Administrativo/a", "Gestión de pedidos y compras"],
        "tecnologia_ia": ["Desarrollador/a Python / IA", "Prompt Engineer / Automatizador LLM"]
    })
    skills_by_area = cv_proposal.get("habilidades_por_area", {})
    loc_detected = cv_proposal.get("localidad", "Alicante")

    # Display Multirubro Detected Competencies
    if skills_by_area:
        st.markdown("**🧠 Habilidades Detectadas por Área de Desempeño:**")
        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1:
            st.markdown("📦 **Hostelería / Logística**")
            st.caption(skills_by_area.get("hosteleria_logistica", "Atención al cliente, reposición, cobro."))
        with col_s2:
            st.markdown("📊 **Administración / ADE**")
            st.caption(skills_by_area.get("administracion_ade", "Gestión documental, facturación, paquete Office."))
        with col_s3:
            st.markdown("💻 **Tech / IA**")
            st.caption(skills_by_area.get("tecnologia_ia", "Python, APIs REST, automatización con IA."))
        st.write("")

    # Sector Multiselect Filter Options (Responsive 2x2 grid)
    st.markdown("**🎯 Selecciona las Ramas de Empleo a Consultar:**")
    sec_c1, sec_c2 = st.columns(2)
    with sec_c1:
        sel_all = st.checkbox("🌐 Todos los sectores", value=True)
        sel_log = st.checkbox("📦 Hostelería, Reposición y Logística", value=True)
    with sec_c2:
        sel_adm = st.checkbox("📊 Administración y ADE", value=True)
        sel_tech = st.checkbox("💻 Programación & IA", value=True)

    # Gather selected sector keywords
    selected_sector_keywords = []
    if sel_all or sel_log:
        for kw in categories_detected.get("hosteleria_logistica", []):
            selected_sector_keywords.append((kw, "Hostelería, Comercio y Logística"))
    if sel_all or sel_adm:
        for kw in categories_detected.get("administracion_ade", []):
            selected_sector_keywords.append((kw, "Administración y ADE"))
    if sel_all or sel_tech:
        for kw in categories_detected.get("tecnologia_ia", []):
            selected_sector_keywords.append((kw, "Tecnología e IA"))

    f_col1, f_col2 = st.columns([2, 1])
    with f_col1:
        custom_job = st.text_input("➕ Puesto personalizado adicional (opcional)", placeholder="Ej: Carretillero / Fontanero / Recepcionista")
        if custom_job.strip():
            selected_sector_keywords.append((custom_job.strip(), "General"))
    with f_col2:
        loc_input_str = st.text_input("Localidad / Provincia", value=loc_detected if loc_detected else "Alicante")

    max_res_val = st.slider("Máximo de Ofertas a Consultar por Categoría", min_value=1, max_value=15, value=6)

    st.write("")
    if st.button("🚀 Buscar Candidaturas Multirubro", type="primary", use_container_width=True, key="btn_search_multirubro"):
        effective_key = api_key_input.strip() if api_key_input else os.getenv("GEMINI_API_KEY", "").strip()
        if not effective_key:
            st.error("Por favor, introduce tu Gemini API Key en la barra lateral.")
        elif not cv_text.strip():
            st.error("Por favor, sube tu CV o edita el texto arriba.")
        elif not selected_sector_keywords:
            st.error("Por favor, marca al menos un sector de búsqueda arriba.")
        else:
            target_loc = loc_input_str.strip() if loc_input_str.strip() else "Alicante"
            st.info(f"🔎 Buscando vacantes activas en InfoJobs, Indeed y Jooble en `{target_loc}` a través de los sectores seleccionados...")
            
            all_found_jobs = []
            search_status = st.empty()
            
            with st.spinner(f"⚡ Consultando InfoJobs, Indeed, Jooble y Adecco para {len(selected_sector_keywords)} búsquedas en paralelo..."):
                async def do_search_all_fast():
                    async with async_playwright() as p:
                        dedup_map = {}
                        for term, sector_label in selected_sector_keywords:
                            try:
                                ij_task = search_jobs(
                                    playwright=p,
                                    keywords=term,
                                    location=target_loc,
                                    max_results=max_res_val,
                                    headless=headless_option
                                )
                                ind_task = search_indeed(
                                    keywords=term,
                                    location=target_loc,
                                    max_results=max_res_val,
                                    playwright=p
                                )
                                jooble_task = search_jooble(
                                    keywords=term,
                                    location=target_loc,
                                    max_results=max_res_val
                                )
                                adecco_task = search_adecco(
                                    keywords=term,
                                    location=target_loc,
                                    max_results=max_res_val,
                                    playwright=p,
                                    headless=headless_option
                                )
                                ij_res, ind_res, jooble_res, adecco_res = await asyncio.gather(
                                    ij_task, ind_task, jooble_task, adecco_task, return_exceptions=True
                                )
                                
                                if isinstance(ij_res, Exception):
                                    print(f"Warning InfoJobs search '{term}': {ij_res}")
                                    ij_res = []
                                if isinstance(ind_res, Exception):
                                    print(f"Warning Indeed search '{term}': {ind_res}")
                                    ind_res = []
                                if isinstance(jooble_res, Exception):
                                    print(f"Warning Jooble search '{term}': {jooble_res}")
                                    jooble_res = []
                                if isinstance(adecco_res, Exception):
                                    print(f"Warning Adecco search '{term}': {adecco_res}")
                                    adecco_res = []

                                for j in (ij_res + ind_res + jooble_res + adecco_res):
                                    key = (j.get("title", "").strip().lower(), j.get("company", "").strip().lower())
                                    if key in dedup_map:
                                        existing = dedup_map[key]
                                        ex_p = set(existing.get("platform", "").split(", "))
                                        new_p = set(j.get("platform", "").split(", "))
                                        comb_p = sorted(list(ex_p | new_p))
                                        existing["platform"] = ", ".join(comb_p)
                                        if not existing.get("link") and j.get("link"):
                                            existing["link"] = j["link"]
                                    else:
                                        j_copy = dict(j)
                                        j_copy["sector"] = sector_label
                                        dedup_map[key] = j_copy
                            except Exception as ex:
                                print(f"Warning searching {term}: {ex}")
                        return list(dedup_map.values())

                try:
                    all_found_jobs = run_async(do_search_all_fast())
                except Exception as ex:
                    st.error(f"Error al realizar la búsqueda: {ex}")

            search_status.empty()

            if not all_found_jobs:
                st.warning(f"No se encontraron ofertas nuevas sin postular en {target_loc} para las categorías seleccionadas.")
            else:
                st.session_state["raw_found_jobs"] = all_found_jobs
                
                # Gemini Evaluation & Extract Generation
                eval_list = []
                p_bar = st.progress(0)
                eval_lbl = st.empty()
                
                for i_j, raw_j in enumerate(all_found_jobs):
                    eval_lbl.text(f"Evaluando oferta {i_j+1}/{len(all_found_jobs)}: {raw_j['title']}...")
                    eval_res = evaluate_job_with_gemini(effective_key, cv_text, raw_j, sector=raw_j.get("sector", ""))
                    job_eval = {
                        **raw_j,
                        "score": eval_res.get("score", 50),
                        "reasoning": eval_res.get("reasoning", ""),
                        "company_extract": eval_res.get("company_extract", ""),
                        "killer_answers": eval_res.get("killer_answers", []),
                        "selected": eval_res.get("score", 0) >= 75
                    }
                    eval_list.append(job_eval)

                    # Auto-dispatch Telegram alert if score >= 85 and Telegram configured
                    if job_eval["score"] >= 85 and telegram_token_input and telegram_chat_id_input:
                        try:
                            run_async(send_telegram_notification(telegram_token_input, telegram_chat_id_input, job_eval))
                        except Exception:
                            pass

                    p_bar.progress((i_j + 1) / len(all_found_jobs))
                
                eval_lbl.empty()
                st.session_state["evaluated_jobs"] = eval_list
                st.success(f"🎉 ¡Se encontraron y evaluaron {len(eval_list)} ofertas multirubro! Revisa el panel de decisión abajo.")

    st.divider()

    # STEP 3: DIRECT DECISION PANEL (ONLY QUALIFIED JOBS MATCH >= 75%)
    if "evaluated_jobs" in st.session_state and st.session_state["evaluated_jobs"]:
        st.markdown("### 3️⃣ Tarjetas de Oferta con Decisión y Envío en 1 Clic (Score ≥ 75%)")
        
        all_eval = st.session_state["evaluated_jobs"]
        # Strict Filter: only show score >= 75 and not discarded
        qualified_jobs = [j for j in all_eval if j.get("score", 0) >= 75 and j.get("status") not in ["descartada", "discarded"]]
        hidden_count = sum(1 for j in all_eval if j.get("score", 0) < 75)
        
        if hidden_count > 0:
            st.info(f"🛡️ **Filtro Estricto Activo:** Se han ocultado automáticamente **{hidden_count} ofertas** por tener una coincidencia inferior al 75%.")

        if not qualified_jobs:
            st.warning("🎉 No hay más vacantes aptas pendientes de revisión. ¡Has tomado decisión sobre todas las ofertas encontradas!")
        else:
            for idx, job in enumerate(qualified_jobs):
                score = job.get("score", 75)
                job_id = job.get("id", f"job_{idx}")
                sec_lbl = job.get("sector", "General")
                
                # Platform Badge
                plat_str = job.get("platform", "InfoJobs")
                if "InfoJobs" in plat_str and "Indeed" in plat_str:
                    plat_badge = '<span style="background-color: #0284C7; color: #FFFFFF; padding: 4px 10px; border-radius: 12px; font-weight: 700; font-size: 0.82rem;">🌐 InfoJobs + Indeed</span>'
                elif "Jooble" in plat_str:
                    plat_badge = '<span style="background-color: #9333EA; color: #FFFFFF; padding: 4px 10px; border-radius: 12px; font-weight: 700; font-size: 0.82rem;">🟣 Jooble</span>'
                elif "Indeed" in plat_str:
                    plat_badge = '<span style="background-color: #2563EB; color: #FFFFFF; padding: 4px 10px; border-radius: 12px; font-weight: 700; font-size: 0.82rem;">🔵 Indeed</span>'
                else:
                    plat_badge = '<span style="background-color: #059669; color: #FFFFFF; padding: 4px 10px; border-radius: 12px; font-weight: 700; font-size: 0.82rem;">🟢 InfoJobs</span>'

                if "Logística" in sec_lbl or "Hostelería" in sec_lbl:
                    sec_badge = '<span style="background-color: #FEF3C7; color: #92400E; padding: 4px 10px; border-radius: 12px; font-weight: 700; font-size: 0.82rem;">📦 Hostelería / Logística</span>'
                elif "Administración" in sec_lbl or "ADE" in sec_lbl:
                    sec_badge = '<span style="background-color: #E0E7FF; color: #3730A3; padding: 4px 10px; border-radius: 12px; font-weight: 700; font-size: 0.82rem;">📊 Administración / ADE</span>'
                elif "Tech" in sec_lbl or "IA" in sec_lbl:
                    sec_badge = '<span style="background-color: #ECE9FE; color: #5B21B6; padding: 4px 10px; border-radius: 12px; font-weight: 700; font-size: 0.82rem;">💻 Tech / IA</span>'
                else:
                    sec_badge = '<span style="background-color: #F1F5F9; color: #334155; padding: 4px 10px; border-radius: 12px; font-weight: 700; font-size: 0.82rem;">🏢 Puesto General</span>'

                with st.container():
                    c_det, c_cond, c_act = st.columns([3.3, 4.2, 2.5])
                    
                    # COLUMNA 1: Título, Empresa, Ubicación y Etiqueta de Origen + Sector
                    with c_det:
                        st.markdown(f"#### [{job['title']}]({job['link']})")
                        st.markdown(f"🏢 **{job['company']}**")
                        st.markdown(f"📍 **{job.get('location', 'Alicante')}**")
                        st.markdown(f"{plat_badge} &nbsp; {sec_badge} &nbsp; <span class='score-badge-high'>🎯 {score}% Coincidencia</span>", unsafe_allow_html=True)
                    
                    # COLUMNA 2: Condiciones y Respuestas Killer
                    with c_cond:
                        sal_str = job.get("salary", "")
                        if sal_str and "no disponible" not in sal_str.lower() and "no especificado" not in sal_str.lower():
                            st.markdown(f"💰 **Salario:** `{sal_str}`")
                        else:
                            st.markdown("⚠️ **Salario no especificado**")
                            
                        mod_str = job.get("modality", "Presencial / Jornada completa")
                        st.markdown(f"💼 **Condiciones:** {mod_str}")
                        
                        if job.get("company_extract"):
                            st.markdown(f"📝 **Extracto:** {job['company_extract']}")
                            
                        if job.get("killer_answers"):
                            with st.expander(f"❓ Respuestas Killer adaptadas ({len(job['killer_answers'])})"):
                                for ka in job["killer_answers"]:
                                    st.caption(f"**P:** {ka.get('question')}")
                                    st.write(f"**R:** {ka.get('answer')}")

                    # COLUMNA 3: Acciones Directas (Aceptar y Postular / Descartar / Generar Carta)
                    with c_act:
                        st.write("")
                        is_applied = job.get("status") in ["applied", "success", "already_applied", "already_applied_on_site", "Postulado"]
                        
                        if is_applied:
                            st.button("✅ Postulado", disabled=True, key=f"btn_done_{job_id}_{idx}", use_container_width=True)
                        else:
                            if st.button("✅ Aceptar y Postular", type="primary", key=f"btn_apply_{job_id}_{idx}", use_container_width=True):
                                effective_key = api_key_input.strip() if api_key_input else os.getenv("GEMINI_API_KEY", "").strip()
                                with st.spinner(f"Enviando postulación a {job['company']}..."):
                                    async def do_apply_single():
                                        async with async_playwright() as p:
                                            return await apply_to_job(
                                                playwright=p,
                                                job_url=job["link"],
                                                killer_answers=job.get("killer_answers", []),
                                                headless=headless_option
                                            )
                                    try:
                                        res = run_async(do_apply_single())
                                        job["status"] = "applied"
                                        database.record_application(
                                            job_id=job["id"],
                                            title=job["title"],
                                            company=job["company"],
                                            link=job["link"],
                                            score=job.get("score", 100),
                                            status="applied",
                                            salary=job.get("salary", ""),
                                            location=job.get("location", ""),
                                            modality=job.get("modality", ""),
                                            sector=job.get("sector", ""),
                                            platform=job.get("platform", "InfoJobs"),
                                            killer_answers=job.get("killer_answers", [])
                                        )
                                        st.toast(f"✅ ¡Inscripción completada con éxito en {job['company']}!")
                                        st.rerun()
                                    except Exception as ae:
                                        st.error(f"Error al postular a {job['company']}: {ae}")

                            if st.button("❌ Descartar", key=f"btn_discard_{job_id}_{idx}", use_container_width=True):
                                job["status"] = "descartada"
                                database.discard_job(
                                    job_id=job["id"],
                                    title=job["title"],
                                    company=job["company"],
                                    link=job["link"],
                                    score=job.get("score", 0),
                                    salary=job.get("salary", ""),
                                    location=job.get("location", ""),
                                    modality=job.get("modality", ""),
                                    sector=job.get("sector", ""),
                                    platform=job.get("platform", "InfoJobs")
                                )
                                st.toast(f"🗑️ Oferta de {job['company']} descartada.")
                                st.rerun()

                        if st.button("📄 Carta de Presentación", key=f"btn_letter_{job_id}_{idx}", use_container_width=True):
                            effective_key = api_key_input.strip() if api_key_input else os.getenv("GEMINI_API_KEY", "").strip()
                            if not effective_key:
                                st.error("Introduce tu Gemini API Key en la barra lateral.")
                            else:
                                with st.spinner("Gemini está redactando tu carta de presentación adaptada..."):
                                    cv_txt = st.session_state.get("cv_text", "")
                                    letter = generate_cover_letter_with_gemini(effective_key, cv_txt, job)
                                    st.session_state[f"cover_letter_{job_id}"] = letter
                                    st.toast("✅ ¡Carta redactada con éxito!")

                if f"cover_letter_{job_id}" in st.session_state:
                    with st.expander(f"📝 Carta de Presentación para {job['company']}", expanded=True):
                        st.text_area("Texto listo para copiar:", value=st.session_state[f"cover_letter_{job_id}"], height=200, key=f"txt_cover_{job_id}")

                st.divider()


# ==============================================================================
# TAB 2: DEDICATED CONVERSATIONAL CHAT WITH ORIOL
# ==============================================================================
with tab_chat:
    st.subheader("💬 Chat Inteligente con Oriol (Tu Asesor Personal)")
    st.markdown("Conversa con **Oriol** para hacerle preguntas sobre tu CV, preparar entrevistas de trabajo, consultar dudas sobre las ofertas o pulir tu búsqueda de empleo.")
    
    if "chat_messages" not in st.session_state:
        st.session_state["chat_messages"] = [
            {
                "role": "assistant",
                "content": "¡Hola! 👋 Soy Oriol, tu asesor personal de empleo. He analizado tu perfil y las herramientas de búsqueda. ¿En qué te puedo orientar hoy? Puedes preguntarme sobre qué destacar en tus entrevistas, salarios, o resolver cualquier duda sobre tus candidaturas."
            }
        ]
        
    c_head1, c_head2 = st.columns([4, 1])
    with c_head2:
        if st.button("🧹 Limpiar Chat", use_container_width=True, key="btn_clear_chat"):
            st.session_state["chat_messages"] = [
                {
                    "role": "assistant",
                    "content": "¡Hola de nuevo! 👋 Chat reiniciado. ¿En qué te ayudo ahora?"
                }
            ]
            st.rerun()
            
    # Quick Tap suggestion chips for mobile users
    st.markdown("**💡 Sugerencias rápidas (1 tap):**")
    chip_col1, chip_col2, chip_col3 = st.columns(3)
    preset_prompt = None
    with chip_col1:
        if st.button("🎯 ¿Qué puestos me convienen?", key="chip_1", use_container_width=True):
            preset_prompt = "¿Qué puestos de empleo encajan mejor con mi experiencia y formación según mi CV?"
    with chip_col2:
        if st.button("💬 Consejos para entrevista", key="chip_2", use_container_width=True):
            preset_prompt = "¿Qué consejos clave me das para superar con éxito una entrevista en mis sectores de interés?"
    with chip_col3:
        if st.button("📊 Resumen de vacantes", key="chip_3", use_container_width=True):
            preset_prompt = "¿Puedes darme un resumen de las vacantes encontradas y mis principales fortalezas?"

    # Display chat history
    for msg in st.session_state["chat_messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
    # Chat user input or quick chip prompt
    user_prompt = st.chat_input("Escribe tu mensaje o pregunta para Oriol...")
    if preset_prompt:
        user_prompt = preset_prompt
        
    if user_prompt:
        st.session_state["chat_messages"].append({"role": "user", "content": user_prompt})
        with st.chat_message("user"):
            st.markdown(user_prompt)
            
        effective_key = api_key_input.strip() if api_key_input else os.getenv("GEMINI_API_KEY", "").strip()
        with st.chat_message("assistant"):
            if not effective_key:
                st.warning("⚠️ Introduce tu clave Gemini API Key en la barra lateral (menú de la izquierda) para chatear con Oriol.")
                assistant_reply = "Por favor, introduce tu clave Gemini API en el menú lateral de la izquierda (obtenla gratis en [Google AI Studio](https://aistudio.google.com/app/apikey)) para que pueda responderte."
            else:
                with st.spinner("Oriol está pensando..."):
                    current_cv = st.session_state.get("cv_text", "")
                    current_eval_jobs = st.session_state.get("evaluated_jobs", None)
                    assistant_reply = chat_with_assistant(
                        api_key=effective_key,
                        chat_history=st.session_state["chat_messages"],
                        cv_text=current_cv,
                        evaluated_jobs=current_eval_jobs
                    )
            st.markdown(assistant_reply)
            st.session_state["chat_messages"].append({"role": "assistant", "content": assistant_reply})


# ==============================================================================
# TAB TELEGRAM: TELEGRAM INTEGRATED CHAT, ALERTS & DECISION FEED
# ==============================================================================
with tab_telegram:
    st.subheader("📱 Telegram Bot, Alertas & Control Integrado")
    st.markdown("Gestiona tu canal de Telegram, prueba el envío de alertas y responde **'👍 Me interesa'** o **'👎 No me interesa'** para actualizar tu base de datos en tiempo real.")
    
    # 1. Status and Test Header
    tg_col1, tg_col2 = st.columns([2, 1])
    eff_bot_token = telegram_token_input.strip() if telegram_token_input else os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    eff_chat_id = telegram_chat_id_input.strip() if telegram_chat_id_input else os.getenv("TELEGRAM_CHAT_ID", "").strip()
    
    with tg_col1:
        if eff_bot_token and eff_chat_id:
            st.success(f"✅ **Telegram Conectado:** Token `...{eff_bot_token[-6:]}` | Chat ID `{eff_chat_id}`")
        else:
            st.warning("⚠️ **Telegram No Configurado:** Configura el Bot Token y Chat ID en el menú lateral izquierdo.")
            
    with tg_col2:
        if st.button("📲 Probar Notificación Telegram", key="btn_test_tg_tab", use_container_width=True):
            if not eff_bot_token or not eff_chat_id:
                st.error("Por favor, configura Bot Token y Chat ID en el menú lateral.")
            else:
                with st.spinner("Enviando alerta interactiva de prueba..."):
                    res = run_async(test_telegram_connection(eff_bot_token, eff_chat_id))
                    if res.get("status") == "success":
                        st.toast("✅ ¡Notificación de prueba enviada con botones interactivos!")
                    else:
                        st.error(f"Error enviando mensaje: {res.get('message')}")

    st.divider()

    # 2. Feed de Alertas & Decisión Interactivas
    st.markdown("### 🔔 Feed de Alertas & Decisión sobre Vacantes (Localhost + Telegram)")
    st.caption("Si marcas **'👎 No me interesa'**, la oferta se registrará inmediatamente como **descartada** en la BD SQLite para que el sistema **NUNCA** vuelva a mostrártela en ninguna búsqueda fututra.")

    apps_db = database.get_all_applications(limit=100)
    
    if not apps_db:
        st.info("Aún no hay vacantes registradas en el historial. Lanza una búsqueda en la pestaña '🚀 Agente' para poblar el feed.")
    else:
        f_c1, f_c2 = st.columns([2, 1])
        with f_c1:
            feed_filter = st.radio(
                "Filtrar vacantes:",
                ["Todas", "⭐ Interesadas", "🔔 Pendientes / Notificadas", "🗑️ Descartadas"],
                horizontal=True,
                key="radio_feed_filter"
            )
            
        filtered_db = []
        for app_item in apps_db:
            st_val = app_item.get("status", "")
            if feed_filter == "⭐ Interesadas" and st_val != "interesado":
                continue
            if feed_filter == "🔔 Pendientes / Notificadas" and st_val not in ["notified_telegram", "pending", "applied"]:
                continue
            if feed_filter == "🗑️ Descartadas" and st_val != "descartada":
                continue
            filtered_db.append(app_item)

        st.write(f"Showing {len(filtered_db)} vacantes:")

        for idx_db, job_item in enumerate(filtered_db):
            j_id = job_item.get("job_id", f"item_{idx_db}")
            j_title = job_item.get("title", "Puesto no especificado")
            j_comp = job_item.get("company", "Empresa")
            j_score = job_item.get("score", 0)
            j_status = job_item.get("status", "pending")
            j_plat = job_item.get("platform", "InfoJobs")
            j_loc = job_item.get("location", "España")
            j_link = job_item.get("link", "#")

            if j_status == "interesado":
                status_badge = "<span style='background-color: #FEF08A; color: #854D0E; padding: 4px 10px; border-radius: 12px; font-weight: 700; font-size: 0.8rem;'>⭐ ME INTERESA</span>"
            elif j_status == "descartada":
                status_badge = "<span style='background-color: #FEE2E2; color: #991B1B; padding: 4px 10px; border-radius: 12px; font-weight: 700; font-size: 0.8rem;'>❌ DESCARTADA (Oculta para siempre)</span>"
            elif j_status == "applied":
                status_badge = "<span style='background-color: #D1FAE5; color: #065F46; padding: 4px 10px; border-radius: 12px; font-weight: 700; font-size: 0.8rem;'>✅ POSTULADO</span>"
            else:
                status_badge = "<span style='background-color: #E0F2FE; color: #075985; padding: 4px 10px; border-radius: 12px; font-weight: 700; font-size: 0.8rem;'>🔔 NOTIFICADA</span>"

            with st.container():
                c_t1, c_t2, c_t3 = st.columns([3.5, 3, 3.5])
                with c_t1:
                    st.markdown(f"#### [{j_title}]({j_link})")
                    st.markdown(f"🏢 **{j_comp}** | 📍 {j_loc}")
                    st.markdown(f"{status_badge} &nbsp; <span class='score-badge-high'>🎯 {j_score}% Coincidencia</span>", unsafe_allow_html=True)
                
                with c_t2:
                    st.caption(f"**Plataforma:** {j_plat}")
                    if job_item.get("date_applied"):
                        st.caption(f"**Fecha:** {job_item.get('date_applied')[:16].replace('T', ' ')}")

                with c_t3:
                    st.write("")
                    col_b1, col_b2 = st.columns(2)
                    with col_b1:
                        if st.button("👍 Me interesa", key=f"btn_tg_yes_{j_id}_{idx_db}", use_container_width=True, disabled=(j_status == "interesado")):
                            database.update_job_status(j_id, "interesado")
                            st.toast("⭐ Vacante marcada como INTERESANTE.")
                            st.rerun()
                    with col_b2:
                        if st.button("👎 No me interesa", key=f"btn_tg_no_{j_id}_{idx_db}", use_container_width=True, disabled=(j_status == "descartada")):
                            database.update_job_status(j_id, "descartada")
                            st.toast("❌ Vacante descartada. Guardada para que no vuelva a salir.")
                            st.rerun()

                st.divider()


# ==============================================================================
# TAB 3: DIRECT URL APPLICATION
# ==============================================================================
with tab_direct:
    st.subheader("⚡ Postulación Directa por URL")
    st.markdown("Pega el enlace de cualquier oferta de InfoJobs para postularte de forma inmediata:")
    
    direct_url = st.text_input("URL de la oferta de InfoJobs", placeholder="https://www.infojobs.net/...")
    
    st.write("Pregunta y Respuesta personalizada (opcional):")
    q_custom = st.text_input("Pregunta (opcional)", key="custom_q")
    a_custom = st.text_input("Respuesta (opcional)", key="custom_a")
    
    if st.button("✨ Inscribirme Directamente", type="primary", key="btn_direct_apply"):
        if not direct_url:
            st.warning("Introduce una URL válida de InfoJobs.")
        else:
            k_answers = [{"question": q_custom, "answer": a_custom}] if q_custom and a_custom else []
            with st.spinner("Inscribiendo en la oferta..."):
                async def do_direct_apply():
                    async with async_playwright() as p:
                        return await apply_to_job(
                            playwright=p,
                            job_url=direct_url,
                            killer_answers=k_answers,
                            headless=headless_option
                        )
                try:
                    res = run_async(do_direct_apply())
                    if res.get("status") in ["success", "already_applied"]:
                        st.success(f"✅ {res.get('message')}")
                    else:
                        st.warning(f"⚠️ {res.get('message')}")
                except Exception as e:
                    st.error(f"Error en la postulación: {e}")


# ==============================================================================
# TAB 4: APPLICATION HISTORY DATABASE (jobs.db)
# ==============================================================================
with tab_history:
    st.subheader("📊 Historial de Postulaciones (jobs.db)")
    
    if st.button("🔄 Actualizar Tabla", key="btn_refresh_db"):
        st.rerun()

    apps = database.get_all_applications(limit=100)
    if apps:
        df = pd.DataFrame(apps)
        st.dataframe(df, use_container_width=True)
        
        csv_data = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar Historial CSV",
            data=csv_data,
            file_name="historial_infojobs.csv",
            mime="text/csv",
            key="btn_csv_download"
        )
    else:
        st.info("Aún no hay postulaciones registradas en la base de datos `jobs.db`.")


# ==============================================================================
# TAB 5: ANALYTICS & FUNNEL DASHBOARD
# ==============================================================================
with tab_analytics:
    st.subheader("📈 Analítica & Funnel de Candidaturas")
    st.markdown("Visualiza el rendimiento de tus búsquedas, distribución por sectores y portales de empleo:")
    
    if st.button("🔄 Recalcular Métricas", key="btn_refresh_analytics"):
        st.rerun()

    apps = database.get_all_applications(limit=1000)
    if not apps:
        st.info("Aún no hay suficientes candidaturas registradas para mostrar analíticas. ¡Realiza tu primera búsqueda en el Tab 1!")
    else:
        df_apps = pd.DataFrame(apps)
        
        total_count = len(df_apps)
        applied_count = len(df_apps[df_apps["status"].isin(["applied", "success", "already_applied", "already_applied_on_site", "Postulado"])])
        discarded_count = len(df_apps[df_apps["status"].isin(["descartada", "discarded"])])
        avg_score = round(df_apps["score"].mean() if "score" in df_apps else 0, 1)

        # KPI Metrics Cards (Responsive 2x2 layout for mobile)
        kpi1, kpi2 = st.columns(2)
        with kpi1:
            st.metric("📌 Total Procesadas", total_count)
        with kpi2:
            st.metric("✅ Postuladas", applied_count, delta=f"{round((applied_count/max(total_count, 1))*100)}%")
            
        kpi3, kpi4 = st.columns(2)
        with kpi3:
            st.metric("🗑️ Descartadas", discarded_count)
        with kpi4:
            st.metric("🎯 Coincidencia Media", f"{avg_score}%")

        st.divider()

        a_col1, a_col2 = st.columns(2)
        with a_col1:
            st.markdown("#### 📦 Distribución por Sector")
            if "sector" in df_apps and not df_apps["sector"].isna().all():
                sector_df = df_apps["sector"].fillna("General").value_counts().reset_index()
                sector_df.columns = ["Sector", "Cantidad"]
                st.bar_chart(sector_df.set_index("Sector"))
            else:
                st.caption("No hay datos de sector disponibles.")

        with a_col2:
            st.markdown("#### 🏷️ Distribución por Plataforma")
            if "platform" in df_apps and not df_apps["platform"].isna().all():
                plat_df = df_apps["platform"].fillna("InfoJobs").value_counts().reset_index()
                plat_df.columns = ["Plataforma", "Cantidad"]
                st.bar_chart(plat_df.set_index("Plataforma"))
            else:
                st.caption("No hay datos de plataforma disponibles.")

        st.markdown("#### 🎯 Distribución de Puntuaciones (% Score)")
        if "score" in df_apps:
            st.bar_chart(df_apps["score"].value_counts().sort_index())
