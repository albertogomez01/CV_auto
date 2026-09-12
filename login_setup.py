import asyncio
import os
import sys
from playwright.async_api import async_playwright
from dotenv import load_dotenv

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

load_dotenv()


STORAGE_STATE_PATH = os.getenv("STORAGE_STATE_PATH", "storageState.json")
INFOJOBS_URL = "https://www.infojobs.net/"

async def run_login_setup():
    print("=" * 60)
    print("   INFOJOBS MANUAL LOGIN SETUP")
    print("=" * 60)
    print("Se abrirá una ventana de Chromium (modo visible).")
    print("Inicia sesión manualmente en tu cuenta de InfoJobs.")
    print("Acepta las cookies si aparecen.")
    print("Una vez hayas iniciado sesión completamente y estés en el panel principal:")
    print("-> Vuelve a esta terminal y presiona ENTER para guardar la sesión.")
    print("=" * 60)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--start-maximized"
            ]
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="es-ES",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        print(f"Navegando a {INFOJOBS_URL} ...")
        await page.goto(INFOJOBS_URL, wait_until="networkidle")

        # Wait for user confirmation in console
        input("\n[PRESIONA ENTER CUANDO HAYAS INICIADO SESIÓN EN EL NAVEGADOR] ... ")

        print("Guardando el estado de la sesión en:", STORAGE_STATE_PATH)
        await context.storage_state(path=STORAGE_STATE_PATH)
        print("¡Sesión guardada correctamente!")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_login_setup())
