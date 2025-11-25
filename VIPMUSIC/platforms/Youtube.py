# youtube.py
# FINAL PERFECT BUILD + RAILWAY AUTO COOKIE REFRESH

import os
import re
import glob
import random
import asyncio
import logging
import functools
import subprocess
import threading
import time
from typing import Optional, Dict, Any, List

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch
from playwright.async_api import async_playwright

# =====================================================
# CONFIG
# =====================================================

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")  # optional

COOKIE_DIR = "cookies"
COOKIE_FILE = os.path.join(COOKIE_DIR, "youtube.txt")

DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "downloads")
TIMEOUT = int(os.getenv("YTDL_TIMEOUT", "300"))

YT_EMAIL = os.getenv("YT_EMAIL", "sthfsuh154@gmail.com")
YT_PASSWORD = os.getenv("YT_PASSWORD", "143@Frnds")

REFRESH_INTERVAL = 60 * 60 * 4  # 4 hours

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(COOKIE_DIR, exist_ok=True)

YT_REGEX = re.compile(r"(youtube\.com|youtu\.be)", re.I)
ANSI_REGEX = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


# =====================================================
# LOGGER
# =====================================================

logger = logging.getLogger("vipmusic.youtube")
if not logger.handlers:
    h = logging.StreamHandler()
    f = logging.Formatter("[%(asctime)s] [YOUTUBE] %(levelname)s: %(message)s")
    h.setFormatter(f)
    logger.addHandler(h)

logger.setLevel(logging.INFO)


# =====================================================
# UTILS
# =====================================================

def safe(func):
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
            return None
    return wrapper


def choose_cookie() -> Optional[str]:
    """Return the single active cookie file"""
    if os.path.exists(COOKIE_FILE) and os.path.getsize(COOKIE_FILE) > 100:
        return COOKIE_FILE
    return None


async def run_blocking(func, *args, **kwargs):
    loop = asyncio.get_running_loop()
    p = functools.partial(func, *args, **kwargs)
    return await loop.run_in_executor(None, p)


def time_to_seconds(duration: str) -> int:
    if not duration:
        return 0
    parts = duration.split(":")
    try:
        return sum(int(p) * 60 ** i for i, p in enumerate(reversed(parts)))
    except Exception:
        return 0


# =====================================================
# AUTO COOKIE REFRESHER (PLAYWRIGHT)
# =====================================================

async def refresh_cookies():
    if not YT_EMAIL or not YT_PASSWORD:
        logger.error("❌ Missing YT_EMAIL / YT_PASSWORD in env variables")
        return

    os.makedirs(COOKIE_DIR, exist_ok=True)

    logger.info("🌐 Launching Playwright for YouTube login...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto("https://accounts.google.com/")
        await page.fill('input[type="email"]', YT_EMAIL)
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(3500)

        await page.fill('input[type="password"]', YT_PASSWORD)
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(9000)

        await page.goto("https://www.youtube.com")
        await page.wait_for_timeout(6000)

        cookies = await context.cookies("https://www.youtube.com")

        with open(COOKIE_FILE, "w", encoding="utf-8") as f:
            f.write("# Netscape HTTP Cookie File\n\n")
            for c in cookies:
                f.write(
                    f"{c['domain']}\t"
                    f"{'TRUE' if c['domain'].startswith('.') else 'FALSE'}\t"
                    f"{c['path']}\t"
                    f"{'TRUE' if c['secure'] else 'FALSE'}\t"
                    f"{int(c['expires']) if c['expires'] else 0}\t"
                    f"{c['name']}\t"
                    f"{c['value']}\n"
                )

        await browser.close()
        logger.info("✅ Cookies refreshed successfully!")


def cookie_daemon():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    while True:
        try:
            loop.run_until_complete(refresh_cookies())
        except Exception as e:
            logger.error(f"Cookie loop error: {e}")
        time.sleep(REFRESH_INTERVAL)


def start_cookie_refresher():
    t = threading.Thread(target=cookie_daemon, daemon=True, name="cookie-refresher")
    t.start()


# Start cookie refresher on boot
start_cookie_refresher()


# =====================================================
# SEARCH
# =====================================================

@safe
async def api_search(query: str, limit: int = 5) -> Optional[List[Dict[str, Any]]]:
    search = VideosSearch(query, limit=limit)
    data = await search.next()

    results = []
    for item in data.get("result", []):
        try:
            thumb = item["thumbnails"][0]["url"].split("?")[0]
        except:
            thumb = None

        results.append({
            "id": item.get("id"),
            "title": item.get("title"),
            "duration": item.get("duration"),
            "duration_sec": time_to_seconds(item.get("duration")),
            "thumb": thumb,
            "channel": item.get("channel", {}).get("name"),
            "link": item.get("link")
        })

    return results


# =====================================================
# MAIN CLASS
# =====================================================

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = ANSI_REGEX

    def exists(self, link: str) -> bool:
        return bool(re.search(self.regex, link, re.I))

    async def from_message(self, message: Message) -> Optional[str]:
        msgs = [message]
        if message.reply_to_message:
            msgs.append(message.reply_to_message)

        for msg in msgs:
            txt = msg.text or msg.caption or ""

            if getattr(msg, "entities", None):
                for e in msg.entities:
                    if e.type == MessageEntityType.URL:
                        return txt[e.offset: e.offset + e.length]

            if getattr(msg, "caption_entities", None):
                for e in msg.caption_entities:
                    if e.type == MessageEntityType.TEXT_LINK:
                        return e.url

        return None

    @safe
    async def details(self, link: str):
        if "&" in link:
            link = link.split("&")[0]

        data = await api_search(link, 1)
        return data[0] if data else None

    @safe
    async def stream(self, link: str):
        if "&" in link:
            link = link.split("&")[0]

        cmd = [
            "yt-dlp",
            "-g",
            "-f",
            "best[height<=?720]",
            link
        ]

        cookie = choose_cookie()
        if cookie:
            cmd.extend(["--cookies", cookie])

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        out, _ = await proc.communicate()
        if not out:
            return None

        cleaned = self.reg.sub("", out.decode(errors="ignore"))
        for line in cleaned.splitlines():
            if line.strip():
                return line.strip()

        return None

    @safe
    async def formats(self, link: str):
        if "&" in link:
            link = link.split("&")[0]

        options = {
            "quiet": True,
            "cookiefile": choose_cookie()
        }

        def extract():
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(link, download=False)

                fmts = []
                for f in info.get("formats", []):
                    fmts.append({
                        "id": f.get("format_id"),
                        "quality": f.get("format_note") or f.get("format"),
                        "ext": f.get("ext"),
                        "size": f.get("filesize")
                    })
                return fmts

        return await run_blocking(extract)

    @safe
    async def download(self, link: str, video=False):
        if "&" in link:
            link = link.split("&")[0]

        ydl_opts = {
            "quiet": True,
            "outtmpl": f"{DOWNLOAD_DIR}/%(id)s.%(ext)s",
            "noplaylist": True,
            "cookiefile": choose_cookie(),
        }

        if video:
            ydl_opts["format"] = "(bestvideo[height<=?720][ext=mp4])+(bestaudio)"
            ydl_opts["merge_output_format"] = "mp4"
        else:
            ydl_opts["format"] = "bestaudio/best"

        def _download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(link, download=True)
                return ydl.prepare_filename(info)

        return await run_blocking(_download)

    @safe
    async def playlist(self, link: str, limit: int = 50):
        if "&" in link:
            link = link.split("&")[0]

        cmd = f'yt-dlp --flat-playlist --get-id --playlist-end {limit} "{link}"'

        cookie = choose_cookie()
        if cookie:
            cmd += f' --cookies "{cookie}"'

        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        out, _ = await proc.communicate()
        if not out:
            return []

        vids = [x.strip() for x in out.decode().split("\n") if x.strip()]
        return [self.base + x for x in vids]


# =====================================================
# GLOBAL INSTANCE
# =====================================================

youtube = YouTubeAPI()
