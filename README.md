# Sistema de Automatización de Postulaciones InfoJobs con Agent Docker

Servicio completo en Python (FastAPI + Playwright Async) para la búsqueda y postulación automática en **InfoJobs** con persistencia de sesión anti-detección, base de datos de deduplicación SQLite y agente autónomo inteligente (**Agent Docker**) guiado por el modelo **Google Gemini 1.5 Pro**.

---

## 🏗️ Arquitectura del Sistema

1. **Gestor de Sesión Anti-Bot (`login_setup.py` & `browser.py`)**:
   - Abre un navegador visible (no-headless) para el inicio de sesión manual inicial.
   - Guarda las cookies y el estado en `storageState.json`.
   - Utiliza `playwright-stealth` para evitar bloqueos y detección de bots.

2. **Servidor API Local (`main.py`)**:
   - `GET /health`: Estado del servicio.
   - `POST /search-jobs`: Busca ofertas según palabras clave y ubicación, descartando las ya postuladas.
   - `POST /apply-job`: Realiza la inscripción automática en la oferta y responde a las *killer questions*.
   - `GET /applications`: Historial de postulaciones registradas en SQLite.

3. **Agente Autónomo Docker (`agent.yml` & `agent_runner.py`)**:
   - Lee la especificación declarativa en `agent.yml`.
   - Evalúa cada vacante devuelta por la API local mediante el modelo **Google Gemini** calculando un porcentaje de coincidencia (score 0-100).
   - Genera respuestas profesionales para las *killer questions* adaptadas al CV base.
   - Postula automáticamente si el `score >= 75%` y emite notificaciones a través de webhooks.

4. **Base de Datos Anti-Duplicados (`database.py`)**:
   - SQLite (`applications.db`) para evitar inscribirse dos veces en la misma oferta (`job_id`).

5. **Interfaz Gráfica Streamlit (`streamlit_app.py`)**:
   - Panel de control visual interactivo para buscar ofertas, iniciar sesión con 1 clic y gestionar postulaciones.

---

## 🚀 Guía de Instalación y Ejecución Paso a Paso

### Paso 1: Configurar Variables de Entorno

Crea un archivo `.env` en la raíz del proyecto basándote en `.env.example`:

```ini
GEMINI_API_KEY=tu_api_key_de_google_gemini
HEADLESS=true
PORT=8000
```

---

### Paso 2: Realizar el Login Inicial Manual (Una Sola Vez)

Para autenticar tu cuenta de InfoJobs y generar las cookies de sesión:

```bash
python login_setup.py
```

1. Se abrirá una ventana del navegador Chromium en InfoJobs.
2. Inicia sesión normalmente con tu correo y contraseña.
3. Presiona ENTER en la terminal cuando estés dentro del panel de usuario.
4. Se generará el archivo `storageState.json`.

---

### Paso 3: Ejecución del Agente Autónomo

#### Opción A: Despliegue con Docker Compose (Recomendado)

Inicia tanto la API como el contenedor del Agente Autónomo con un solo comando:

```bash
docker compose up --build
```

El contenedor del agente se conectará a la API local a través de `http://host.docker.internal:8000` ejecutando el flujo definido en `agent.yml`.

#### Opción B: Ejecución Local en Python

Si prefieres ejecutar los componentes directamente en tu entorno Python local:

1. Arranca la API local:
   ```bash
   python main.py
   ```

2. En otra terminal, ejecuta el agente autónomo:
   ```bash
   python agent_runner.py
   ```

---

## 🛠️ Especificación del Agente (`agent.yml`)

```yaml
version: "1"

model:
  provider: google
  name: gemini-1.5-pro
  api_key: ${GEMINI_API_KEY}

instructions: |
  Eres un asistente autónomo de búsqueda y postulación de empleo para InfoJobs.
  ...
tools:
  - name: search_jobs
    request:
      url: http://host.docker.internal:8000/search-jobs
  - name: apply_to_job
    request:
      url: http://host.docker.internal:8000/apply-job
  - name: send_notification
    request:
      url: https://httpbin.org/post
```

---

## 🖥️ Interfaz Gráfica Interactiva Streamlit (Subida de CV & Selección de Empresas)

Para utilizar la página web interactiva donde puedes subir tu **CV (PDF o TXT)**, consultar el **% de coincidencia**, ver el **extracto de las empresas** y seleccionar a cuáles postularte:

```bash
streamlit run streamlit_app.py
```

Accede automáticamente en tu navegador a: **`http://localhost:8501`**

### Funcionalidades de la Web:
1. **Subida de CV**: Carga tu archivo PDF o pega tu texto directamente.
2. **Evaluación IA con Gemini**: Análisis en tiempo real del % de compatibilidad y resumen ejecutivo de cada empresa.
3. **Tabla de Selección**: Revisa las preguntas *killer* y marca con casillas de verificación las empresas donde deseas inscribirte.
4. **Postulación en Lote**: Envío automático a las ofertas seleccionadas con 1 solo clic.

---

## 📱 Aplicación Móvil Nativa (Expo Go)

Para controlar el bot directamente desde tu teléfono móvil (iOS / Android):

### 1. Arrancar el Backend en tu PC
Ejecuta la API usando el entorno virtual `.venv`:
```powershell
.\.venv\Scripts\python.exe main.py
```

### 2. Iniciar el Servidor de Expo
En otra ventana de la terminal:
```bash
cd mobile
npx expo start
```

### 3. Conectar tu Teléfono
1. Abre la aplicación **Expo Go** en tu móvil.
2. Escanea el **código QR** que aparece en la consola de la terminal de tu PC.
3. ¡Listo! La app se cargará en tu móvil. Podrás buscar ofertas, filtrarlas y postularte con 1 clic desde la pantalla táctil de tu smartphone.


