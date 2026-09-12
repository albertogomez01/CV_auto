# 🚀 Guía de Despliegue 24/7 en la Nube (Linux / Docker Always Free)

Esta guía permite desplegar el sistema en cualquier Servidor Virtual Linux (ej. **Oracle Cloud Free Tier**, **AWS EC2**, **DigitalOcean**, **Hetzner** o cualquier VPS con Docker) de forma 100% autónoma y **sin coste mensual**.

---

## ⚡ Despliegue Rápido en 3 Comandos

### 1. Clonar el repositorio y acceder
```bash
git clone https://github.com/albertogomez01/CV_auto.git && cd CV_auto
```

### 2. Configurar las variables de entorno (`.env`)
```bash
nano .env
```
> Asegúrate de incluir tus claves principales:
> ```env
> GEMINI_API_KEY=tu_gemini_api_key
> TELEGRAM_BOT_TOKEN=8929616203:AAGJ_XAfVo3AeKq_icY3HyJ0sN4ki5H0YVw
> TELEGRAM_CHAT_ID=6270123390
> AUTOPILOT_AUTOSTART=true
> AUTOPILOT_INTERVAL=30
> ```

### 3. Compilar y levantar en segundo plano 24/7
```bash
docker compose up -d --build
```

---

## 🌐 Servicios Disponibles tras el Despliegue

- **Dashboard Web (Streamlit)**: `http://<IP_DE_TU_SERVIDOR>:8501`
- **Backend API (FastAPI)**: `http://<IP_DE_TU_SERVIDOR>:8000/docs`
- **Piloto Automático (Segundo Plano)**: Activado automáticamente enviando notificaciones a tu Telegram cada 30 minutos sin requerir abrir el navegador.

---

## 🔍 Comandos Útiles de Mantenimiento

- **Ver logs en tiempo real**:
  ```bash
  docker compose logs -f
  ```
- **Reiniciar el contenedor**:
  ```bash
  docker compose restart
  ```
- **Detener el servicio**:
  ```bash
  docker compose down
  ```
