# Youtube.py (updated — adds auto-refresh cookies, rotating proxies, Playwright cookie refresh)
import asyncio
import os
import re
import json
from typing import Union
import requests
import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch
from VIPMUSIC.utils.database import is_on_off
from VIPMUSIC import app
from VIPMUSIC.utils.formatters import time_to_seconds
import os
import glob
import random
import logging
import pymongo
from pymongo import MongoClient
import aiohttp
import config
import traceback
from VIPMUSIC import LOGGER
from playwright.async_api import async_playwright
import time
import datetime
import shutil
import pathlib
import sys
import stat
import subprocess

# ========== CONFIG (some new env variables supported) ==========
API_URL = os.getenv("API_URL", "https://teaminflex.xyz")
API_KEY = os.getenv("API_KEY", "INFLEX93454428D")

# YouTube login (used when auto-refreshing cookies)
YT_EMAIL = os.getenv("YT_EMAIL", os.getenv("YT_EMAIL", "sthfsuh@gmail.com"))
YT_PASSWORD = os.getenv("YT_PASSWORD", os.getenv("YT_PASSWORD", "143@Frnds"))

# Toggle auto-refresh cookies (deploy-friendly option). Set to "true" (case-insensitive) to enable.
AUTO_REFRESH_COOKIES = os.getenv("AUTO_REFRESH_COOKIES", "false").lower() in ("1", "true", "yes")

# Proxies: comma-separated strings
YTDLP_PROXIES = os.getenv("YTDLP_PROXIES", "")  # e.g. "http://ip1:port,http://user:pass@ip:port"
PLAYWRIGHT_PROXIES = os.getenv("PLAYWRIGHT_PROXIES", "")  # e.g. same format

# Cookie directory
COOKIES_DIR = os.path.join(os.getcwd(), "cookies")
os.makedirs(COOKIES_DIR, exist_ok=True)

# Logger helper
def get_logger(name: str):
    try:
        return LOGGER(name)
    except Exception:
        log = logging.getLogger(name)
        if not log.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
            log.addHandler(handler)
        log.setLevel(logging.INFO)
        return log

logger = get_logger("HeartBeat/platforms/Youtube.py")

# ========== Utility: Proxy rotation helpers (NEW) ==========
def _parse_proxy_list(proxy_env: str):
    if not proxy_env:
        return []
    # split by comma and strip
    parts = [p.strip() for p in proxy_env.split(",") if p.strip()]
    return parts

YTDLP_PROXY_POOL = _parse_proxy_list(YTDLP_PROXIES)
PLAYWRIGHT_PROXY_POOL = _parse_proxy_list(PLAYWRIGHT_PROXIES)

def choose_random_proxy(pool):
    if not pool:
        return None
    return random.choice(pool)

# ========== COOKIE FILE HELPERS ==========
def cookie_txt_file():
    """
    Return a random cookie txt path from cookies dir, or attempt to refresh automatically if enabled.
    """
    cookie_dir = COOKIES_DIR
    if not os.path.exists(cookie_dir):
        if AUTO_REFRESH_COOKIES:
            logger.info("Cookies directory missing — attempting auto-refresh (AUTO_REFRESH_COOKIES is enabled).")
            try:
                # attempt to refresh cookies
                asyncio.get_event_loop().run_until_complete(refresh_cookies_playwright())
            except Exception as e:
                logger.error(f"Auto-refresh cookies failed: {e}")
        # still not present or creation failed
        if not os.path.exists(cookie_dir):
            return None

    cookies_files = [f for f in os.listdir(cookie_dir) if f.endswith(".txt")]
    if not cookies_files:
        # try auto-refresh if enabled
        if AUTO_REFRESH_COOKIES:
            logger.info("No cookie files found — attempting auto-refresh (AUTO_REFRESH_COOKIES is enabled).")
            try:
                asyncio.get_event_loop().run_until_complete(refresh_cookies_playwright())
            except Exception as e:
                logger.error(f"Auto-refresh cookies failed: {e}")
        cookies_files = [f for f in os.listdir(cookie_dir) if f.endswith(".txt")]
        if not cookies_files:
            return None
    cookie_file = os.path.join(cookie_dir, random.choice(cookies_files))
    return cookie_file

# ========== NEW: Playwright cookie refresh (creates Netscape cookies.txt compatible with yt-dlp) ==========
async def refresh_cookies_playwright(proxy: str = None, headless: bool = True, save_json: bool = False):
    """
    Launch Playwright, sign into YouTube using YT_EMAIL/YT_PASSWORD and save cookies in Netscape cookies.txt format
    compatible with yt-dlp. Returns path to cookie file on success. (NEW)
    - proxy: optional proxy to pass to the browser (e.g. "http://user:pass@ip:port")
    - headless: keep default True for servers like Railway
    - save_json: if True, also saves cookies as JSON for inspection
    """
    log = get_logger("refresh_cookies_playwright")
    if not YT_EMAIL or not YT_PASSWORD:
        raise Exception("YT_EMAIL or YT_PASSWORD not provided; cannot refresh cookies via Playwright.")

    # choose proxy from pool if not provided
    if not proxy:
        proxy = choose_random_proxy(PLAYWRIGHT_PROXY_POOL)

    timestamp = int(time.time())
    cookie_filename = os.path.join(COOKIES_DIR, f"cookie_{timestamp}.txt")
    cookie_json_filename = os.path.join(COOKIES_DIR, f"cookie_{timestamp}.json")

    log.info(f"Starting Playwright cookie refresh. proxy={proxy} headless={headless}")

    try:
        async with async_playwright() as p:
            browser_launch_kwargs = {
                "headless": headless,
                # recommended flags to improve stealth/headless behaviour
                "args": [
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-accelerated-2d-canvas",
                    "--disable-gpu",
                    "--single-process",
                    "--ignore-certificate-errors",
                    "--disable-blink-features=AutomationControlled",
                ],
            }
            if proxy:
                # Playwright expects {"server": "http://ip:port", "username": "...", "password": "..."} or string for server
                # If proxy contains user:pass, pass as server and parse credentials
                proxy_parts = None
                try:
                    if "@" in proxy and "://" in proxy:
                        # format: scheme://user:pass@host:port
                        proto_rest = proxy.split("://", 1)[1]
                        creds, host = proto_rest.split("@", 1)
                        user, pwd = creds.split(":", 1)
                        proxy_parts = {"server": proxy.split("://", 1)[0] + "://" + host, "username": user, "password": pwd}
                    else:
                        proxy_parts = {"server": proxy}
                except Exception:
                    proxy_parts = {"server": proxy}
                browser_launch_kwargs["proxy"] = proxy_parts

            browser = await p.chromium.launch(**browser_launch_kwargs)
            context_kwargs = {
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
                "viewport": {"width": 1280, "height": 800},
                "locale": "en-US",
                "java_script_enabled": True,
            }
            context = await browser.new_context(**context_kwargs)
            page = await context.new_page()

            # Navigate and perform login flow
            # We attempt a resilient login — YouTube / Google behaviour may change; adapt selectors if needed.
            await page.goto("https://accounts.google.com/ServiceLogin?service=youtube", timeout=60000)
            await page.wait_for_load_state("networkidle", timeout=60000)

            # Enter email
            # Note: Google may use different flows (select account or email), we attempt common selectors.
            try:
                # email input
                await page.fill('input[type="email"]', YT_EMAIL)
                await page.click('button[jsname="LgbsSe"], #identifierNext, button:has-text("Next")', timeout=5000)
                await page.wait_for_timeout(1500)
            except Exception:
                # sometimes the input has id 'identifierId'
                try:
                    await page.fill('#identifierId', YT_EMAIL)
                    await page.click('#identifierNext')
                except Exception as e:
                    log.warning(f"Email input flow may differ: {e}")

            # Wait and fill password
            await page.wait_for_timeout(2500)
            try:
                await page.fill('input[type="password"]', YT_PASSWORD)
                await page.click('button[jsname="LgbsSe"], #passwordNext, button:has-text("Next")', timeout=5000)
            except Exception:
                try:
                    await page.fill('input[name="password"]', YT_PASSWORD)
                    await page.click('#passwordNext')
                except Exception as e:
                    log.warning(f"Password input flow may differ: {e}")

            # Wait for possible redirects and network idle
            await page.wait_for_load_state("networkidle", timeout=60000)
            await page.wait_for_timeout(3000)

            # Navigate to youtube to ensure session cookies set
            await page.goto("https://www.youtube.com/", timeout=60000)
            await page.wait_for_load_state("networkidle", timeout=60000)
            await page.wait_for_timeout(3000)

            # Get cookies from context
            cookies = await context.cookies()
            if not cookies:
                raise Exception("No cookies captured after login attempt.")

            # Save as JSON optionally
            if save_json:
                with open(cookie_json_filename, "w", encoding="utf-8") as jf:
                    json.dump(cookies, jf, ensure_ascii=False, indent=2)

            # Convert Playwright cookies to Netscape cookies.txt format for yt-dlp compatibility
            # Netscape format: domain \t flag \t path \t secure \t expiration \t name \t value
            with open(cookie_filename, "w", encoding="utf-8") as f:
                f.write("# Netscape HTTP Cookie File\n")
                for c in cookies:
                    # ensure domain starts with dot for cross subdomains
                    domain = c.get("domain", "")
                    if not domain.startswith("."):
                        domain = "." + domain if domain else domain
                    flag = "TRUE" if c.get("httpOnly", False) else "FALSE"
                    path = c.get("path", "/")
                    secure = "TRUE" if c.get("secure", False) else "FALSE"
                    expires = str(int(c.get("expires", int(time.time() + 3600))))
                    name = c.get("name", "")
                    value = c.get("value", "")
                    # Write line
                    f.write("\t".join([domain, flag, path, secure, expires, name, value]) + "\n")

            await context.close()
            await browser.close()

            log.info(f"Cookies saved to {cookie_filename}")
            return cookie_filename

    except Exception as e:
        log.error(f"Playwright cookie refresh failed: {e}")
        raise

# ========== API helper wrappers with auto-refresh on 401 (NEW) ==========
async def _post_with_api_refresh(url: str, json_payload: dict, headers: dict, session: aiohttp.ClientSession, retries: int = 1):
    """
    Make a POST request to API_URL with provided headers. If response is 401 and AUTO_REFRESH_COOKIES enabled,
    attempt to refresh cookies and retry once (retries param controls attempts).
    Returns the aiohttp response object (not the content).
    (NEW)
    """
    attempt = 0
    last_exception = None
    while attempt <= retries:
        attempt += 1
        try:
            resp = await session.post(url, json=json_payload, headers=headers)
            # if 401 and auto-refresh is enabled, attempt cookie refresh then retry once
            if resp.status == 401:
                # attempt cookie refresh if configured
                logger.warning(f"[API] Received 401 from {url} (attempt {attempt}/{retries+1})")
                if AUTO_REFRESH_COOKIES:
                    try:
                        logger.info("AUTO_REFRESH_COOKIES enabled — attempting to refresh cookies due to 401.")
                        # run refresh synchronously in event loop
                        await refresh_cookies_playwright()
                        # after refresh, retry by continuing loop
                        continue
                    except Exception as e:
                        logger.error(f"Auto refresh during API 401 failed: {e}")
                        # fallthrough and raise after exhausting retries
                # if not enabled or refresh failed: return resp so caller can handle
                return resp
            return resp
        except Exception as e:
            last_exception = e
            logger.error(f"Exception while POST to {url}: {e}")
            if AUTO_REFRESH_COOKIES:
                try:
                    logger.info("Attempting auto-refresh cookies after POST exception.")
                    await refresh_cookies_playwright()
                except Exception as re:
                    logger.error(f"Auto refresh after POST exception failed: {re}")
            # continue to retry loop until attempts exhausted
    # after loop
    if last_exception:
        raise last_exception
    return None

# ========== AUDIO / VIDEO DOWNLOAD LOGIC (kept original behaviour, with small drops for proxies and auto-refresh) ==========
async def download_song(link: str) -> str:
    video_id = link.split('v=')[-1].split('&')[0] if 'v=' in link else link
    logger = get_logger("HeartBeat/platforms/Youtube.py")
    logger.info(f"🎵 [AUDIO] Starting download process for ID: {video_id}")

    if not video_id or len(video_id) < 3:
        return

    DOWNLOAD_DIR = "downloads"
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.webm")

    # local file exists
    if os.path.exists(file_path):
        logger.info(f"🎵 [LOCAL] Found existing file for ID: {video_id}")
        return file_path

    # ------------------------------
    # API FIRST
    # ------------------------------
    try:
        async with aiohttp.ClientSession() as session:
            payload = {"url": video_id, "type": "audio"}
            headers = {"Content-Type": "application/json", "X-API-KEY": API_KEY}

            resp = await _post_with_api_refresh(f"{API_URL}/download", payload, headers, session, retries=1)
            if resp is None:
                raise Exception("No response from API")

            if resp.status == 401:
                logger.error("[API] Invalid API key")
                raise Exception("Invalid API key")

            if resp.status != 200:
                raise Exception(f"API returned {resp.status}")

            data = await resp.json()

            if data.get("status") != "success" or not data.get("download_url"):
                raise Exception(f"[AUDIO] API response error: {data}")

            download_link = f"{API_URL}{data['download_url']}"

            async with session.get(download_link) as file_response:
                if file_response.status != 200:
                    raise Exception(f"[AUDIO] Download failed: {file_response.status}")

                with open(file_path, "wb") as f:
                    async for chunk in file_response.content.iter_chunked(8192):
                        f.write(chunk)

        logger.info(f"🎵 [API] Download completed successfully for ID: {video_id}")
        return file_path

    except Exception as e:
        logger.warning(f"[API AUDIO FAILED] {e} – falling back to yt-dlp")

    # ------------------------------
    # FALLBACK yt-dlp + cookies
    # ------------------------------
    cookie_file = cookie_txt_file()
    if not cookie_file:
        logger.error("No cookies found. Cannot fallback to yt-dlp.")
        return None

    # choose a proxy for yt-dlp if provided
    proxy = choose_random_proxy(YTDLP_PROXY_POOL)
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": file_path,
        "cookiefile": cookie_file,
        "quiet": True,
    }
    if proxy:
        ydl_opts["proxy"] = proxy
        logger.info(f"[yt-dlp] Using proxy: {proxy}")

    try:
        yt_dlp.YoutubeDL(ydl_opts).download([link])
        logger.info(f"[yt-dlp] Audio downloaded for {video_id}")
        return file_path
    except Exception as e:
        logger.error(f"[yt-dlp AUDIO FAILED] {e}")
        return None


async def download_video(link: str) -> str:
    video_id = link.split('v=')[-1].split('&')[0] if 'v=' in link else link
    logger = get_logger("HeartBeat/platforms/Youtube.py")
    logger.info(f"🎥 [VIDEO] Starting download process for ID: {video_id}")

    if not video_id or len(video_id) < 3:
        return

    DOWNLOAD_DIR = "downloads"
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.mkv")

    # local file exists
    if os.path.exists(file_path):
        logger.info(f"🎥 [LOCAL] Found existing file for ID: {video_id}")
        return file_path

    # ------------------------------
    # API FIRST
    # ------------------------------
    try:
        async with aiohttp.ClientSession() as session:
            payload = {"url": video_id, "type": "video"}
            headers = {"Content-Type": "application/json", "X-API-KEY": API_KEY}

            resp = await _post_with_api_refresh(f"{API_URL}/download", payload, headers, session, retries=1)
            if resp is None:
                raise Exception("No response from API")

            if resp.status == 401:
                raise Exception("Invalid API key")

            if resp.status != 200:
                raise Exception(f"[VIDEO] API returned {resp.status}")

            data = await resp.json()

            if data.get("status") != "success" or not data.get("download_url"):
                raise Exception(f"[VIDEO] API response error: {data}")

            download_link = f"{API_URL}{data['download_url']}"

            async with session.get(download_link) as file_response:
                if file_response.status != 200:
                    raise Exception(f"[VIDEO] Download failed: {file_response.status}")

                with open(file_path, "wb") as f:
                    async for chunk in file_response.content.iter_chunked(8192):
                        f.write(chunk)

        logger.info(f"🎥 [API] Download completed successfully for ID: {video_id}")
        return file_path

    except Exception as e:
        logger.warning(f"[API VIDEO FAILED] {e} – falling back to yt-dlp")

    # ------------------------------
    # FALLBACK yt-dlp + cookies
    # ------------------------------
    cookie_file = cookie_txt_file()
    if not cookie_file:
        logger.error("Cookies missing – cannot download video")
        return None

    proxy = choose_random_proxy(YTDLP_PROXY_POOL)
    ydl_opts = {
        "format": "bestvideo+bestaudio/best",
        "outtmpl": file_path,
        "cookiefile": cookie_file,
        "merge_output_format": "mkv",
        "quiet": True,
    }
    if proxy:
        ydl_opts["proxy"] = proxy
        logger.info(f"[yt-dlp] Using proxy: {proxy}")

    try:
        yt_dlp.YoutubeDL(ydl_opts).download([link])
        logger.info(f"[yt-dlp] Video downloaded for {video_id}")
        return file_path
    except Exception as e:
        logger.error(f"[yt-dlp VIDEO FAILED] {e}")
        return None

# ========== SIZE CHECK (keeps logic, adds proxy support and cookie auto-refresh) ==========
async def check_file_size(link):
    async def get_format_info(link):
        cookie_file = cookie_txt_file()
        if not cookie_file:
            print("No cookies found. Cannot check file size.")
            return None

        # choose proxy if available
        proxy = choose_random_proxy(YTDLP_PROXY_POOL)
        proxy_arg = f"--proxy \"{proxy}\"" if proxy else ""

        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--cookies", cookie_file,
            "-J",
            link,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            print(f'Error:\n{stderr.decode()}')
            return None
        return json.loads(stdout.decode())

    def parse_size(formats):
        total_size = 0
        for format in formats:
            if 'filesize' in format and format['filesize']:
                total_size += format['filesize']
        return total_size

    info = await get_format_info(link)
    if info is None:
        return None

    formats = info.get('formats', [])
    if not formats:
        print("No formats found.")
        return None

    total_size = parse_size(formats)
    return total_size

async def shell_cmd(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, errorz = await proc.communicate()
    if errorz:
        if "unavailable videos are hidden" in (errorz.decode("utf-8")).lower():
            return out.decode("utf-8")
        else:
            return errorz.decode("utf-8")
    return out.decode("utf-8")

# ========== YOUTUBE API CLASS (unchanged logic except calling cookie helpers where needed) ==========
class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        for message in messages:
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        return text[entity.offset: entity.offset + entity.length]
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        return None

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            vidid = result["id"]
            duration_sec = int(time_to_seconds(duration_min)) if duration_min else 0
        return title, duration_min, duration_sec, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["title"]

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["duration"]

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["thumbnails"][0]["url"].split("?")[0]

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        try:
            downloaded_file = await download_video(link)
            if downloaded_file:
                return 1, downloaded_file
            else:
                return 0, "Video API did not return a valid file."
        except Exception as e:
            print(f"Video API failed: {e}")
            return 0, f"Video API failed: {e}"

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        cookie_file = cookie_txt_file()
        if not cookie_file:
            return []
        playlist = await shell_cmd(
            f"yt-dlp -i --get-id --flat-playlist --cookies {cookie_file} --playlist-end {limit} --skip-download {link}"
        )
        try:
            result = [key for key in playlist.split("\n") if key]
        except:
            result = []
        return result

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            vidid = result["id"]
            yturl = result["link"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        track_details = {
            "title": title,
            "link": yturl,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail,
        }
        return track_details, vidid

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        cookie_file = cookie_txt_file()
        if not cookie_file:
            return [], link
        ytdl_opts = {"quiet": True, "cookiefile": cookie_file}
        # add proxy if available
        proxy = choose_random_proxy(YTDLP_PROXY_POOL)
        if proxy:
            ytdl_opts["proxy"] = proxy
        ydl = yt_dlp.YoutubeDL(ytdl_opts)
        with ydl:
            formats_available = []
            r = ydl.extract_info(link, download=False)
            for format in r["formats"]:
                try:
                    if "dash" not in str(format["format"]).lower():
                        formats_available.append(
                            {
                                "format": format["format"],
                                "filesize": format.get("filesize"),
                                "format_id": format["format_id"],
                                "ext": format["ext"],
                                "format_note": format["format_note"],
                                "yturl": link,
                            }
                        )
                except:
                    continue
        return formats_available, link

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        a = VideosSearch(link, limit=10)
        result = (await a.next()).get("result")
        title = result[query_type]["title"]
        duration_min = result[query_type]["duration"]
        vidid = result[query_type]["id"]
        thumbnail = result[query_type]["thumbnails"][0]["url"].split("?")[0]
        return title, duration_min, thumbnail, vidid

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> str:
        if videoid:
            link = self.base + link

        try:
            if songvideo or songaudio:
                downloaded_file = await download_song(link)
                if downloaded_file:
                    return downloaded_file, True
                else:
                    return None, False

            elif video:
                downloaded_file = await download_video(link)
                if downloaded_file:
                    return downloaded_file, True
                else:
                    return None, False

            else:
                downloaded_file = await download_song(link)
                if downloaded_file:
                    return downloaded_file, True
                else:
                    return None, False

        except Exception as e:
            print(f"API download failed: {e}")
            return None, False
