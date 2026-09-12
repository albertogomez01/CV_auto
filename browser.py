import os
import json
from typing import Tuple
from playwright.async_api import async_playwright, Playwright, BrowserContext, Page
from playwright_stealth import Stealth
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORAGE_STATE_PATH = os.getenv("STORAGE_STATE_PATH", os.path.join(BASE_DIR, "storageState.json"))
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

USER_DATA_DIR = os.getenv("USER_DATA_DIR", os.path.join(BASE_DIR, "user_data"))

async def get_browser_context(playwright: Playwright, headless: bool = True, use_storage_state: bool = True) -> BrowserContext:
    args = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-infobars",
        "--window-size=1280,800",
        "--disable-dev-shm-usage",
        "--lang=es-ES"
    ]

    browser = await playwright.chromium.launch(
        headless=headless,
        args=args
    )

    context_kwargs = {
        "user_agent": DEFAULT_USER_AGENT,
        "viewport": {"width": 1280, "height": 800},
        "locale": "es-ES",
        "timezone_id": "Europe/Madrid",
        "device_scale_factor": 1,
        "extra_http_headers": {
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "sec-ch-ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"'
        }
    }

    if use_storage_state and os.path.exists(STORAGE_STATE_PATH):
        try:
            with open(STORAGE_STATE_PATH, "r", encoding="utf-8") as f:
                state_data = json.load(f)
                if state_data.get("cookies") or state_data.get("origins"):
                    context_kwargs["storage_state"] = STORAGE_STATE_PATH
                    print(f"[Browser] Cargado estado de sesión desde {STORAGE_STATE_PATH}")
        except Exception as e:
            print(f"[Browser] Warning loading storageState.json: {e}")

    context = await browser.new_context(**context_kwargs)
    return context

async def create_stealth_page(context: BrowserContext) -> Page:
    page = await context.new_page()
    try:
        await Stealth().apply_stealth_async(page)
    except Exception as e:
        print(f"[Browser] Stealth notice: {e}")
    return page
