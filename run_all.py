import os
import sys
import time
import subprocess
import signal
import urllib.request
import json

# Ensure UTF-8 output encoding on Windows terminal
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

PYTHON_BIN = sys.executable

processes = []

def cleanup(signum=None, frame=None):
    print("\n🛑 Deteniendo todos los servicios del sistema...")
    for p, name in processes:
        if p.poll() is None:
            print(f"   Deteniendo {name} (PID: {p.pid})...")
            try:
                p.terminate()
                p.wait(timeout=3)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
    print("✅ Todos los servicios se han detenido correctamente.")
    sys.exit(0)

signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)

def wait_for_api(url: str = "http://localhost:8000/health", timeout: int = 30) -> bool:
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            req = urllib.request.urlopen(url, timeout=2)
            if req.status == 200:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False

def main():
    port = os.getenv("PORT", "8501")
    is_cloud = "PORT" in os.environ

    print("=" * 70)
    print("🚀 INICIANDO SISTEMA COMPLETO DE AUTOMATIZACIÓN DE EMPLEO")
    print("=" * 70)

    # 1. Iniciar FastAPI Backend (puerto 8000 interno)
    print("\n⚡ [1/3] Iniciando Servidor Backend FastAPI (Port 8000)...")
    p_api = subprocess.Popen(
        [PYTHON_BIN, "main.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT
    )
    processes.append((p_api, "FastAPI Backend"))

    print("⏳ Esperando respuesta del Backend API...")
    if wait_for_api():
        print("✅ Backend FastAPI listo y escuchando en http://localhost:8000")
    else:
        print("⚠️ El Backend API tardó en responder, continuando...")

    # 2. Iniciar Dashboard Web Streamlit (Puerto $PORT en 0.0.0.0 para Nube o 8501 local)
    print(f"\n🌐 [2/3] Iniciando Dashboard Web Streamlit (Port {port})...")
    st_cmd = [
        PYTHON_BIN, "-m", "streamlit", "run", "streamlit_app.py",
        "--server.port", str(port),
        "--server.address", "0.0.0.0",
        "--server.headless", "true"
    ]
    p_streamlit = subprocess.Popen(
        st_cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT
    )
    processes.append((p_streamlit, "Dashboard Streamlit"))
    print(f"✅ Dashboard Streamlit listo y escuchando en puerto {port}")

    # 3. Iniciar Bot de Telegram en segundo plano (sin servidor web propio)
    print("\n🤖 [3/3] Iniciando Bot de Telegram en segundo plano...")
    bot_env = os.environ.copy()
    bot_env["DISABLE_BOT_HEALTH_SERVER"] = "1"
    p_bot = subprocess.Popen(
        [PYTHON_BIN, "bot.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        env=bot_env
    )
    processes.append((p_bot, "Bot de Telegram"))
    print("✅ Bot de Telegram activo en segundo plano")

    print("\n" + "=" * 70)
    print("🎉 ¡SISTEMA UNIFICADO EN EJECUCIÓN 24/7!")
    print("=" * 70)
    print(f"  🌐 Dashboard Web:   {'https://tu-app.onrender.com' if is_cloud else 'http://localhost:' + str(port)}")
    print("  ⚡ API Backend:      http://localhost:8000 (Documentación: http://localhost:8000/docs)")
    print("  🤖 Bot Telegram:    Escuchando eventos en tiempo real")
    print("\nPresiona CTRL+C en cualquier momento para detener todos los servicios.")
    print("=" * 70 + "\n")

    # Si se pasa el argumento --run-agent, ejecutar una ronda inicial del agente
    if "--run-agent" in sys.argv or "-a" in sys.argv:
        print("🤖 Ejecutando ciclo inicial del Agente Autónomo...")
        try:
            subprocess.run([PYTHON_BIN, "agent_runner.py"])
        except Exception as e:
            print(f"⚠️ Error al ejecutar el agente autónomo: {e}")

    # Mantener el proceso principal vivo monitorizando los subprocesos
    try:
        while True:
            time.sleep(2)
            for p, name in processes:
                if p.poll() is not None:
                    print(f"⚠️ Aviso: El servicio '{name}' se ha detenido (código {p.returncode}). Reintentando...")
                    # Reiniciar subproceso si cae
                    if name == "FastAPI Backend":
                        new_p = subprocess.Popen([PYTHON_BIN, "main.py"], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
                    elif name == "Dashboard Streamlit":
                        new_p = subprocess.Popen(st_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
                    elif name == "Bot de Telegram":
                        new_p = subprocess.Popen([PYTHON_BIN, "bot.py"], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT, env=bot_env)
                    processes.remove((p, name))
                    processes.append((new_p, name))
    except KeyboardInterrupt:
        cleanup()

if __name__ == "__main__":
    main()
