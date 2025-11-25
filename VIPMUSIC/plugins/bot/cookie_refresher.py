import os
import json
from playwright.async_api import async_playwright

COOKIE_DIR = f"{os.getcwd()}/cookies"
COOKIE_FILE = f"{COOKIE_DIR}/youtube.txt"

YT_EMAIL = os.getenv("YT_EMAIL", os.getenv("YT_EMAIL", "sthfsuh@gmail.com"))
YT_PASSWORD = os.getenv("YT_PASSWORD", os.getenv("YT_PASSWORD", "143@Frnds"))

async def refresh_youtube_cookies():
    if not YT_EMAIL or not YT_PASSWORD:
        print("❌ YT_EMAIL or YT_PASSWORD not found in env")
        return None

    os.makedirs(COOKIE_DIR, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled"
            ]
        )

        context = await browser.new_context()
        page = await context.new_page()

        print("🌐 Opening YouTube login page...")
        await page.goto("https://accounts.google.com/signin/v2/identifier")

        await page.wait_for_selector('input[type="email"]')
        await page.fill('input[type="email"]', YT_EMAIL)
        await page.click("#identifierNext")
        await page.wait_for_timeout(3000)

        await page.wait_for_selector('input[type="password"]', timeout=60000)
        await page.fill('input[type="password"]', YT_PASSWORD)
        await page.click("#passwordNext")
        await page.wait_for_timeout(8000)

        print("✅ Login success, saving cookies...")

        cookies = await context.cookies()
        with open(COOKIE_FILE, "w", encoding="utf-8") as f:
            for cookie in cookies:
                f.write(
                    f'{cookie["domain"]}\tTRUE\t{cookie["path"]}\t'
                    f'{"TRUE" if cookie["secure"] else "FALSE"}\t'
                    f'{int(cookie["expires"])}\t'
                    f'{cookie["name"]}\t{cookie["value"]}\n'
                )

        await browser.close()
        print(f"✅ Cookies saved to: {COOKIE_FILE}")
        return COOKIE_FILE


async def ensure_cookies():
    if not os.path.exists(COOKIE_FILE) or os.path.getsize(COOKIE_FILE) < 10:
        print("🔁 Cookies missing or empty – refreshing...")
        return await refresh_youtube_cookies()

    # Optional: refresh every 24h
    if (os.path.getmtime(COOKIE_FILE) + 86400) < os.path.getmtime(__file__):
        print("🔁 Cookies expired – refreshing...")
        return await refresh_youtube_cookies()

    print("✅ Cookies OK")
    return COOKIE_FILE
