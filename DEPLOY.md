# 🚀 Guía de Uso y Despliegue de CV_auto

CV_auto está diseñado para ser **intuitivo, limpio y fácil de usar** para cualquier persona, con 0 fricción técnica.

---

## 📱 Opción 1: Uso Directo desde Telegram (Fricción Cero)
*La forma más sencilla para nuevos usuarios. No requiere instalar nada ni tocar código.*

1. **Abre el Bot en Telegram:** Entra al enlace de tu bot (ejemplo: `https://t.me/TuBot`).
2. **Pulsa `/start`:** El asistente conversacional te guiará paso a paso en 3 preguntas rápidas:
   - 🎯 **Paso 1:** ¿Qué puesto o empleo buscas?
   - 📍 **Paso 2:** ¿En qué ciudad o provincia (o 'Remoto')?
   - 📄 **Paso 3:** Adjunta tu Currículum en PDF/TXT (o escribe un resumen).
3. **¡Listo!** El sistema rastreará los portales de empleo de forma automática cada 30 minutos y te enviará las mejores ofertas a tu chat con botones interactivos (⭐ **Me interesa** / ❌ **Descartar**).

### Comandos útiles en Telegram:
- `/miperfil` ➔ Revisa o edita tu configuración guardada.
- `/pausar` ➔ Suspende temporalmente las notificaciones.
- `/reanudar` ➔ Reactiva el envío de ofertas.
- `/start` ➔ Reinicia el asistente para cambiar de puesto o ciudad.

---

## 🌐 Opción 2: App Web en la Nube (Estilo App Móvil)
*Accede a tu panel interactivo desde cualquier navegador (Móvil o PC).*

1. **Accede a la URL Web:** Abre la dirección de tu aplicación (ejemplo: `https://tu-app.onrender.com`).
2. **Interfaz Intuitiva:**
   - 🚀 **Agente:** Sube tu CV y pulsa *"Buscar Candidaturas"* para consultar vacantes cuando quieras.
   - 💬 **Chat Oriol:** Habla con tu asesor de empleo IA para resolver dudas y preparar entrevistas.
   - 📊 **Historial:** Consulta todas las ofertas evaluadas y genera cartas de presentación en 1 clic.

---

## ⚙️ Opción 3: Despliegue 24/7 para Administradores (Render / VPS)

### Despliegue en Render (Recomendado Gratuito 24/7):
1. Conecta tu repositorio en **Render.com**.
2. Configura las siguientes variables de entorno:
   - `GEMINI_API_KEY`: Tu clave de Google AI Studio.
   - `TELEGRAM_BOT_TOKEN`: Token otorgado por @BotFather.
   - `DATABASE_URL`: URI de PostgreSQL (ej. Supabase o Neon).
   - `HEADLESS`: `true`
3. Comando de inicio (**Start Command**):
   ```bash
   python run_all.py
   ```

### Despliegue Local o en Servidor VPS (Docker):
```bash
# 1. Clonar el repositorio
git clone https://github.com/albertogomez01/CV_auto.git && cd CV_auto

# 2. Iniciar todos los servicios
python run_all.py
```
