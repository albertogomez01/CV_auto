import os
import sys
import json
import yaml
import re
import requests
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv()

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def normalize_url(url: str) -> str:
    # 1. Allow explicit override via environment variable
    override_base = os.getenv("API_BASE_URL")
    if override_base:
        parts = url.split("/", 3)
        path = "/" + parts[3] if len(parts) > 3 else ""
        return f"{override_base.rstrip('/')}{path}"
        
    # 2. Convert host.docker.internal according to environment
    if "host.docker.internal" in url:
        if os.getenv("RUNNING_IN_DOCKER"):
            # Inside Docker Compose network, talk directly to the 'api' container
            return url.replace("host.docker.internal", "api")
        else:
            # On host machine, connect to localhost
            return url.replace("host.docker.internal", "localhost")
    return url

import time

def make_request_with_fallback(url: str, json_payload: Dict[str, Any], headers: Dict[str, str], timeout: int = 180, max_retries_per_url: int = 3) -> requests.Response:
    target_urls = [normalize_url(url)]
    
    # Add fallback URLs if primary fails
    if "api:8000" in target_urls[0]:
        target_urls.append(url) # fallback to host.docker.internal
    elif "host.docker.internal:8000" in target_urls[0]:
        target_urls.append(url.replace("host.docker.internal", "api"))
        target_urls.append(url.replace("host.docker.internal", "localhost"))

    last_error = None
    for target in target_urls:
        for attempt in range(1, max_retries_per_url + 1):
            try:
                res = requests.post(target, json=json_payload, headers=headers, timeout=timeout)
                res.raise_for_status()
                return res
            except Exception as e:
                last_error = e
                if attempt < max_retries_per_url:
                    time.sleep(3)
                else:
                    print(f"[HTTP Request] Reintento fallido en '{target}': {e}. Probando alternativa...")
    raise last_error


def load_agent_config(config_path: str = "agent.yml") -> Dict[str, Any]:
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"No se encontró el archivo de configuración: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def get_gemini_client(api_key: str):
    """Initializes Gemini API client using available SDK (google-genai or google-generativeai)."""
    try:
        from google import genai
        return ("genai_new", genai.Client(api_key=api_key))
    except ImportError:
        try:
            import google.generativeai as genai_old
            genai_old.configure(api_key=api_key)
            return ("genai_old", genai_old)
        except ImportError:
            return ("http", api_key)

def evaluate_job_with_gemini(client_info: tuple, model_name: str, cv_instructions: str, job: Dict[str, Any]) -> Dict[str, Any]:
    """Uses Gemini model to score job against CV and answer killer questions with multirubro rules."""
    client_type, client = client_info
    
    sector_info = f"\n- SECTOR DE LA VACANTE: {job.get('sector', '')}\n" if job.get('sector') else ""
    
    prompt = f"""
{cv_instructions}

Debes evaluar la siguiente vacante de empleo recibida:{sector_info}
- Título: {job.get('title', '')}
- Empresa: {job.get('company', '')}
- Enlace: {job.get('link', '')}
- Descripción: {job.get('description', '')}
- Preguntas de filtrado (Killer Questions): {json.dumps(job.get('killer_questions', []), ensure_ascii=False)}

REGLAS DE PONDERACIÓN SEGÚN EL SECTOR DE LA VACANTE:
- Hostelería, Comercio, Reposición y Logística: pondera atención al cliente, actitud servicial/agilidad, cobro en caja, reposición, picking y preparación de pedidos.
- Administración y Gestión (Perfil ADE): pondera organización, tareas de auxiliar administrativo, facturación, soporte contable y paquete Office.
- Tecnología e Inteligencia Artificial: pondera desarrollo en Python, integración de APIs REST, automatización de procesos y modelos LLM.

TAREA:
1. Analiza detenidamente el perfil CV y la descripción del puesto adaptando el enfoque al sector de la vacante.
2. OBLIGATORIO: Calcula una puntuación de coincidencia (score) del 0 al 100 basada en habilidades, experiencia e idiomas.
3. OBLIGATORIO: Si hay preguntas de filtrado (killer questions), genera respuestas coherentes, profesionales y en primera persona basadas en el CV y adaptadas al sector.
4. Responde ÚNICAMENTE con un objeto JSON válido con la siguiente estructura exacta (sin formato markdown alrededor ni texto adicional):

{{
  "score": 85,
  "reasoning": "Breve explicación de la puntuación...",
  "killer_answers": [
    {{
      "question": "Texto exacto de la pregunta",
      "answer": "Respuesta optimizada"
    }}
  ]
}}
"""

    response_text = ""
    # Clean model name candidates for high compatibility with Google GenAI API
    candidate_models = []
    if model_name:
        candidate_models.append(model_name)
    for default_m in ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash", "gemini-pro"]:
        if default_m not in candidate_models:
            candidate_models.append(default_m)

    last_model_error = None
    for m in candidate_models:
        try:
            if client_type == "genai_new":
                response = client.models.generate_content(
                    model=m,
                    contents=prompt
                )
                response_text = response.text
            elif client_type == "genai_old":
                gen_model = client.GenerativeModel(m)
                response = gen_model.generate_content(prompt)
                response_text = response.text
            else:
                # HTTP direct API fallback
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={client}"
                headers = {"Content-Type": "application/json"}
                payload = {"contents": [{"parts": [{"text": prompt}]}]}
                res = requests.post(url, headers=headers, json=payload, timeout=30)
                res.raise_for_status()
                data = res.json()
                response_text = data['candidates'][0]['content']['parts'][0]['text']

            # If succeeded, break loop
            break
        except Exception as err:
            last_model_error = err
            print(f"[Gemini Evaluator] Aviso: fallo con modelo '{m}' ({err}). Probando siguiente candidato...")

    if not response_text and last_model_error:
        print(f"[Gemini Evaluator] Aviso: Gemini API no disponible ({last_model_error}). Usando evaluación heurística inteligente...")
        title = job.get('title', '')
        description = job.get('description', '')
        company = job.get('company', '')
        words_cv = set(re.findall(r'\w+', cv_instructions.lower()))
        words_job = set(re.findall(r'\w+', f"{title} {description} {company}".lower()))
        stopwords = {"de", "la", "el", "en", "y", "a", "los", "del", "se", "con", "un", "para", "por", "las", "su", "es", "eres", "un", "una"}
        cv_kws = {w for w in words_cv if len(w) > 3 and w not in stopwords}
        job_kws = {w for w in words_job if len(w) > 3 and w not in stopwords}
        matches = cv_kws.intersection(job_kws) if job_kws else set()
        calc_score = min(95, max(65, int(65 + (len(matches) / max(1, len(job_kws))) * 35)))
        return {
            "score": calc_score,
            "reasoning": f"Evaluación heurística de respaldo por palabras clave ({len(matches)} términos coincidentes).",
            "killer_answers": []
        }


    # Clean markdown backticks if returned by model
    clean_json = response_text.strip()
    if clean_json.startswith("```"):
        lines = clean_json.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        clean_json = "\n".join(lines).strip()

    try:
        parsed = json.loads(clean_json)
        return parsed
    except json.JSONDecodeError as e:
        print(f"[Gemini Evaluator] Error al parsear JSON devuelto por Gemini: {e}")
        print(f"[Gemini Evaluator] Respuesta raw: {response_text}")
        return {"score": 0, "reasoning": "Error al parsear respuesta JSON", "killer_answers": []}

def run_agent():
    print("=" * 60)
    print("🤖 INICIANDO AGENTE AUTÓNOMO DE POSTULACIÓN DE EMPLEO")
    print("=" * 60)

    # 1. Load config
    config = load_agent_config("agent.yml")
    instructions = config.get("instructions", "")
    model_cfg = config.get("model", {})
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        api_key_env_var = model_cfg.get("api_key", "${GEMINI_API_KEY}")
        if api_key_env_var.startswith("${") and api_key_env_var.endswith("}"):
            var_name = api_key_env_var[2:-1]
            api_key = os.getenv(var_name)
        else:
            api_key = api_key_env_var

    if not api_key or api_key == "${GEMINI_API_KEY}":
        print("❌ ERROR: La variable de entorno GEMINI_API_KEY no está configurada.")
        print("Por favor, configura GEMINI_API_KEY en tu archivo .env o en el entorno.")
        sys.exit(1)

    model_name = model_cfg.get("name", "gemini-1.5-pro")
    print(f"🔹 Modelo configurado: {model_name}")

    # Map tools by name
    tools_map = {t["name"]: t for t in config.get("tools", [])}
    search_tool = tools_map.get("search_jobs")
    apply_tool = tools_map.get("apply_to_job")
    notify_tool = tools_map.get("send_notification")

    if not search_tool or not apply_tool:
        print("❌ ERROR: Las herramientas 'search_jobs' y 'apply_to_job' deben estar definidas en agent.yml.")
        sys.exit(1)

    # 2. Step 1: Search Jobs
    search_req = search_tool.get("request", {})
    raw_search_url = search_req.get("url")
    search_body = search_req.get("body", {})

    print(f"\n🔍 [Paso 1] Consultando ofertas de trabajo en: {raw_search_url}")
    print(f"   Parámetros: {search_body}")

    try:
        res = make_request_with_fallback(raw_search_url, search_body, search_req.get("headers", {}), timeout=180)
        search_data = res.json()
    except Exception as e:
        print(f"❌ Error al conectar con la API de búsqueda ({raw_search_url}): {e}")
        print("Asegúrate de que el servidor FastAPI está en ejecución (`python main.py`).")
        sys.exit(1)

    jobs = search_data.get("data", [])
    print(f"✅ Ofertas encontradas no postuladas anteriormente: {len(jobs)}")

    if not jobs:
        print("ℹ️ No hay nuevas vacantes para procesar en este momento.")
        return

    # Initialize Gemini client
    gemini_client = get_gemini_client(api_key)

    # 3. Step 2 & 3 & 4: Process each job
    applied_count = 0
    for idx, job in enumerate(jobs, start=1):
        title = job.get("title", "Sin título")
        company = job.get("company", "Sin empresa")
        link = job.get("link", "")
        
        print(f"\n------------------------------------------------------------")
        print(f"📄 [{idx}/{len(jobs)}] Evaluando vacante: '{title}' ({company})")
        print(f"   Link: {link}")

        # Evaluate with Gemini
        eval_res = evaluate_job_with_gemini(gemini_client, model_name, instructions, job)
        score = eval_res.get("score", 0)
        reasoning = eval_res.get("reasoning", "")
        killer_answers = eval_res.get("killer_answers", [])

        print(f"📊 Coincidencia calculada: {score}%")
        if reasoning:
            print(f"💡 Justificación: {reasoning}")
        if killer_answers:
            print(f"❓ Respuestas a Killer Questions generadas: {len(killer_answers)}")

        # Threshold check >= 75
        if score >= 75:
            print(f"🎯 Score >= 75% -> Procediendo a la postulación automática...")

            # Call apply_to_job tool
            apply_req = apply_tool.get("request", {})
            raw_apply_url = apply_req.get("url")
            
            apply_payload = {
                "job_url": link,
                "killer_answers": killer_answers
            }

            try:
                apply_res = make_request_with_fallback(raw_apply_url, apply_payload, apply_req.get("headers", {}), timeout=180)
                apply_out = apply_res.json()
                print(f"✅ Postulación enviada con éxito: {apply_out.get('message', 'Completado')}")
                applied_count += 1

                # Send Notification tool
                if notify_tool:
                    notify_req = notify_tool.get("request", {})
                    raw_notify_url = notify_req.get("url")
                    notify_payload = {
                        "event": "job_application_completed",
                        "job_title": title,
                        "company": company,
                        "score": score,
                        "link": link
                    }
                    try:
                        make_request_with_fallback(raw_notify_url, notify_payload, notify_req.get("headers", {}), timeout=30)
                        print(f"🔔 Notificación registrada.")
                    except Exception as ne:
                        print(f"⚠️ Error al enviar notificación: {ne}")

            except Exception as ae:
                print(f"❌ Error al postular a la oferta: {ae}")
        else:
            print(f"⏭️ Score inferior a 75% ({score}%). Se omite esta vacante.")


    print(f"\n============================================================")
    print(f"🎉 PROCESO FINALIZADO: {applied_count} postulaciones completadas de {len(jobs)} evaluadas.")
    print(f"============================================================")

if __name__ == "__main__":
    run_agent()
