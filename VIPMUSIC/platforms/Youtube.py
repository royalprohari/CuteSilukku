# youtube.py
# FINAL PERFECT BUILD for VIPMUSIC
# Includes: Search, Stream, Download, Playlist, Formats + Auto Cookie Refresher

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


# =====================================================
# CONFIG
# =====================================================

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")  # optional
COOKIE_DIR = os.getenv("YTDL_COOKIE_DIR", "{os.getcwd()}/cookies")
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "downloads")
TIMEOUT = int(os.getenv("YTDL_TIMEOUT", "300"))

BROWSERS = ["chrome", "firefox", "edge", "opera", "brave"]
REFRESH_INTERVAL = 60 * 60 * 4  # 4 hours

# API extras (as provided at bottom of user's file)
API_URL = "https://teaminflex.xyz"
API_KEY = "INFLEX93454428D"

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
    """
    Async-only decorator to catch exceptions and log them.
    Returns None on error.
    """
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
            return None
    return wrapper


def choose_cookie() -> Optional[str]:
    """
    Return a random cookie file path from COOKIE_DIR, or None.
    """
    try:
        files = glob.glob(os.path.join(COOKIE_DIR, "*.txt"))
        return random.choice(files) if files else None
    except Exception as e:
        logger.debug(f"choose_cookie error: {e}")
        return None


def cookie_txt_file() -> Optional[str]:
    """
    Alternate helper (keeps backward compatibility with your bottom helper).
    Uses the same COOKIE_DIR constant.
    """
    try:
        if not os.path.exists(COOKIE_DIR):
            return None
        cookies_files = [f for f in os.listdir(COOKIE_DIR) if f.endswith(".txt")]
        if not cookies_files:
            return None
        return os.path.join(COOKIE_DIR, random.choice(cookies_files))
    except Exception as e:
        logger.debug(f"cookie_txt_file error: {e}")
        return None


async def run_blocking(func, *args, **kwargs):
    """
    Run a blocking function in a thread pool.
    """
    loop = asyncio.get_running_loop()
    p = functools.partial(func, *args, **kwargs)
    return await loop.run_in_executor(None, p)


def time_to_seconds(duration: str) -> int:
    """
    Convert H:MM:SS or M:SS to seconds. Returns 0 for falsy input.
    """
    if not duration:
        return 0
    parts = duration.split(":")
    try:
        return sum(int(p) * 60 ** i for i, p in enumerate(reversed(parts)))
    except Exception:
        return 0


# =====================================================
# AUTO COOKIE REFRESHER
# =====================================================

def refresh_browser_cookies():
    """
    Run yt-dlp to export cookies from known browsers into COOKIE_DIR.
    Each browser's cookies are written to <COOKIE_DIR>/<browser>.txt
    """
    for browser in BROWSERS:
        out_file = os.path.join(COOKIE_DIR, f"{browser}.txt")

        cmd = [
            "yt-dlp",
            "--cookies-from-browser", browser,
            "--cookies", out_file,
            "--skip-download",
            "https://www.youtube.com"
        ]

        try:
            subprocess.run(
                cmd,
                timeout=60,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            if os.path.exists(out_file) and os.path.getsize(out_file) > 500:
                logger.info(f"✅ Cookies refreshed: {browser}")
            else:
                logger.warning(f"⚠️ Cookie file too small or missing for: {browser}")
        except Exception as e:
            logger.error(f"{browser} cookie refresh error: {e}", exc_info=True)


def cookie_daemon():
    """
    Daemon that refreshes browser cookies every REFRESH_INTERVAL seconds.
    """
    while True:
        try:
            logger.debug("Starting cookie refresh cycle")
            refresh_browser_cookies()
        except Exception as e:
            logger.error(f"cookie_daemon loop error: {e}")
        time.sleep(REFRESH_INTERVAL)


def start_cookie_refresher():
    """
    Start cookie refresher in a daemon thread.
    """
    t = threading.Thread(target=cookie_daemon, daemon=True, name="cookie-refresher")
    t.start()


# start refreshing immediately
start_cookie_refresher()


# =====================================================
# SEARCH
# =====================================================

@safe
async def api_search(query: str, limit: int = 5) -> Optional[List[Dict[str, Any]]]:
    """
    Uses youtubesearchpython to perform a search and return a simplified list.
    """
    try:
        search = VideosSearch(query, limit=limit)
        data = await search.next()

        results = []
        for item in data.get("result", []):
            thumb = None
            try:
                thumb = item.get("thumbnails")[0]["url"].split("?")[0]
            except Exception:
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
    except Exception as e:
        logger.error(f"api_search failed: {e}", exc_info=True)
        return None


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
        """
        Extract a URL from a pyrogram Message or its reply's message.
        """
        msgs = [message]
        if message.reply_to_message:
            msgs.append(message.reply_to_message)

        for msg in msgs:
            txt = msg.text or msg.caption or ""

            # entities (URL)
            if getattr(msg, "entities", None):
                for e in msg.entities:
                    if e.type == MessageEntityType.URL:
                        return txt[e.offset: e.offset + e.length]

            # caption entities (TEXT_LINK)
            if getattr(msg, "caption_entities", None):
                for e in msg.caption_entities:
                    if e.type == MessageEntityType.TEXT_LINK:
                        return e.url

        return None

    # ---------------- DETAILS ---------------- #
    @safe
    async def details(self, link: str) -> Optional[Dict[str, Any]]:
        """
        Return details using api_search for a single item.
        """
        if "&" in link:
            link = link.split("&")[0]

        data = await api_search(link, 1)
        return data[0] if data else None

    # ---------------- STREAM URL ---------------- #
    @safe
    async def stream(self, link: str) -> Optional[str]:
        """
        Return a direct stream URL (first line) using yt-dlp -g with constraints.
        """
        if "&" in link:
            link = link.split("&")[0]

        cmd = [
            "yt-dlp",
            "-g",
            "-f",
            "best[height<=?720][width<=?1280]",
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
            logger.debug("yt-dlp returned no stdout for stream")
            return None

        # strip ANSI escapes, decode, and return first non-empty line
        cleaned = self.reg.sub("", out.decode(errors="ignore")).strip()
        for line in cleaned.splitlines():
            if line.strip():
                return line.strip()
        return None

    # ---------------- FORMATS ---------------- #
    @safe
    async def formats(self, link: str):
        """
        Return available formats (format id, quality note, ext, size) using yt_dlp Python API.
        """
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
                    # some formats lack format_note; include reasonable ones
                    note = f.get("format_note") or f.get("format") or f.get("format_id")
                    fmts.append({
                        "id": f.get("format_id"),
                        "quality": note,
                        "ext": f.get("ext"),
                        "size": f.get("filesize")
                    })
                return fmts

        return await run_blocking(extract)

    # ---------------- DOWNLOAD ---------------- #
    @safe
    async def download(self, link: str, video: bool = False) -> Optional[str]:
        """
        Download audio (default) or video (if video=True). Returns final filename or None.
        """
        if "&" in link:
            link = link.split("&")[0]

        # try to pick a cookie; fallback to None (yt_dlp handles None)
        cookie_choice = choose_cookie()

        ydl_opts = {
            "quiet": True,
            "outtmpl": f"{DOWNLOAD_DIR}/%(id)s.%(ext)s",
            "noplaylist": True,
            "geo_bypass": True,
            "nocheckcertificate": True,
            "cookiefile": cookie_choice
        }

        if video:
            ydl_opts["format"] = "(bestvideo[height<=?720][ext=mp4])+(bestaudio)"
            ydl_opts["merge_output_format"] = "mp4"
        else:
            ydl_opts["format"] = "bestaudio/best"

        def _download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(link, download=True)
                # prepare_filename requires the info dict returned by extract_info
                return ydl.prepare_filename(info)

        return await run_blocking(_download)

    # ---------------- PLAYLIST ---------------- #
    @safe
    async def playlist(self, link: str, limit: int = 50) -> List[str]:
        """
        Return list of video watch URLs from a playlist using yt-dlp --flat-playlist.
        """
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
            logger.debug("yt-dlp returned no stdout for playlist")
            return []

        vids = [x.strip() for x in out.decode(errors="ignore").split("\n") if x.strip()]
        return [self.base + x for x in vids]


# =====================================================
# GLOBAL INSTANCE
# =====================================================

youtube = YouTubeAPI()
