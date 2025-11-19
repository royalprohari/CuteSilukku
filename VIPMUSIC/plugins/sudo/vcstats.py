from pyrogram import filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
import asyncio
import time

from pyrogram.errors import MessageNotModified

from VIPMUSIC import app
from VIPMUSIC.misc import SUDOERS
from VIPMUSIC.utils.database import get_active_chats, get_active_video_chats
from config import BANNED_USERS, START_IMG_URL


# =============================================================
# MEMORY CACHE (FAST REFRESH BOOSTER)
# =============================================================
_cache = {
    "audio": [],
    "video": [],
    "timestamp": 0
}

CACHE_DURATION = 5  # seconds


async def get_cached_stats():
    """Return audio/video stats from cache if fresh, else fetch new."""
    global _cache

    now = time.time()
    if now - _cache["timestamp"] <= CACHE_DURATION:
        return _cache["audio"], _cache["video"]

    audio = await get_active_chats()
    video = await get_active_video_chats()

    _cache["audio"] = audio
    _cache["video"] = video
    _cache["timestamp"] = now

    return audio, video


# =============================================================
# UTIL: Pagination
# =============================================================
def paginate_list(items, page, per_page=10):
    start = (page - 1) * per_page
    end = start + per_page
    sliced = items[start:end]
    total_pages = (len(items) - 1) // per_page + 1 if items else 1
    return sliced, total_pages


# =============================================================
# SAFE EDIT HELPER (avoids MESSAGE_NOT_MODIFIED)
# =============================================================
async def safe_edit_caption(msg: Message, caption: str, reply_markup: InlineKeyboardMarkup = None):
    """
    Edit message caption only if different. If caption is same, try to edit reply_markup only.
    Swallows MESSAGE_NOT_MODIFIED errors.
    """
    try:
        existing = msg.caption or ""
        if existing.strip() == (caption or "").strip():
            if reply_markup is not None:
                try:
                    await msg.edit_reply_markup(reply_markup)
                except Exception:
                    # ignore reply_markup edit errors
                    pass
            return
        await msg.edit_caption(caption, reply_markup=reply_markup)
    except MessageNotModified:
        # message unchanged; try to update reply_markup if provided
        if reply_markup is not None:
            try:
                await msg.edit_reply_markup(reply_markup)
            except Exception:
                pass
        return
    except Exception as e:
        # non-fatal: log and continue
        print("[vcstats] safe_edit_caption error:", e)


# =============================================================
# COMMAND: /vcstats
# =============================================================
@app.on_message(
    filters.command(["vcstats", "vcs", "vct"], prefixes=["/", "!", "%", ",", ".", "@", "#"])
    & ~BANNED_USERS
)
async def vcstats_handler(client, msg: Message):

    if msg.from_user.id not in SUDOERS:
        return await msg.reply_text("❌ Only SUDO users can use this command.")

    return await send_stats(msg, auto_cycle=False)


# =============================================================
# SEND INITIAL VC STATS
# =============================================================
async def send_stats(message, auto_cycle):

    audio, video = await get_cached_stats()

    audio_count = len(audio)
    video_count = len(video)

    # STATUS LIGHTS
    audio_light = "🟢" if audio_count > 0 else "🔴"
    video_light = "🟢" if video_count > 0 else "🔴"

    caption = (
        "📊 **Live VC Statistics**\n"
        "•━━━━━━━━━━━━━━━━━━•\n"
        f"{audio_light} 🎧 **Audio Active:** `{audio_count}`\n"
        f"{video_light} 🎥 **Video Active:** `{video_count}`\n"
        "•━━━━━━━━━━━━━━━━━━•\n"
        "⏳ *Refreshing every 10 seconds…*\n" if auto_cycle else ""
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🎧 Audio Chats", callback_data="vc_audio_page_1"),
                InlineKeyboardButton("🎥 Video Chats", callback_data="vc_video_page_1"),
            ],
            [
                InlineKeyboardButton("🔁 Refresh", callback_data="vc_refresh_manual"),
                InlineKeyboardButton("⏳ Auto-Refresh", callback_data="vc_enable_autorefresh"),
            ],
            [
                InlineKeyboardButton("❌ Close", callback_data="vc_close"),
            ]
        ]
    )

    return await message.reply_photo(START_IMG_URL, caption=caption, reply_markup=keyboard)


# =============================================================
# MANUAL REFRESH
# =============================================================
@app.on_callback_query(filters.regex("^vc_refresh_manual$"))
async def vc_refresh_manual(client, cq: CallbackQuery):

    if cq.from_user.id not in SUDOERS:
        return await cq.answer("❌ Unauthorized", show_alert=True)

    audio, video = await get_cached_stats()

    audio_light = "🟢" if len(audio) > 0 else "🔴"
    video_light = "🟢" if len(video) > 0 else "🔴"

    caption = (
        "📊 **Live VC Statistics (Refreshed)**\n"
        "•━━━━━━━━━━━━━━━━━━•\n"
        f"{audio_light} 🎧 **Audio Active:** `{len(audio)}`\n"
        f"{video_light} 🎥 **Video Active:** `{len(video)}`\n"
        "•━━━━━━━━━━━━━━━━━━•"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🎧 Audio Chats", callback_data="vc_audio_page_1"),
                InlineKeyboardButton("🎥 Video Chats", callback_data="vc_video_page_1"),
            ],
            [
                InlineKeyboardButton("🔁 Refresh", callback_data="vc_refresh_manual"),
                InlineKeyboardButton("⏳ Auto-Refresh", callback_data="vc_enable_autorefresh"),
            ],
            [
                InlineKeyboardButton("❌ Close", callback_data="vc_close"),
            ]
        ]
    )

    await safe_edit_caption(cq.message, caption, keyboard)
    await cq.answer("🔁 Updated")


# =============================================================
# AUTO REFRESH
# =============================================================
@app.on_callback_query(filters.regex("^vc_enable_autorefresh$"))
async def vc_enable_autorefresh(client, cq: CallbackQuery):

    if cq.from_user.id not in SUDOERS:
        return await cq.answer("❌ Unauthorized", show_alert=True)

    await cq.answer("⏳ Auto-refresh started")

    msg = cq.message

    # Loop for ~5 minutes (10 seconds each)
    for _ in range(30):
        try:
            audio, video = await get_cached_stats()

            audio_light = "🟢" if len(audio) > 0 else "🔴"
            video_light = "🟢" if len(video) > 0 else "🔴"

            caption = (
                "📊 **Live VC Statistics (Auto)**\n"
                "•━━━━━━━━━━━━━━━━━━•\n"
                f"{audio_light} 🎧 **Audio Active:** `{len(audio)}`\n"
                f"{video_light} 🎥 **Video Active:** `{len(video)}`\n"
                "•━━━━━━━━━━━━━━━━━━•\n"
                "⏳ Auto-refreshing every 10 seconds…"
            )

            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("🎧 Audio Chats", callback_data="vc_audio_page_1"),
                        InlineKeyboardButton("🎥 Video Chats", callback_data="vc_video_page_1"),
                    ],
                    [
                        InlineKeyboardButton("🛑 Stop Auto", callback_data="vc_stop_autorefresh"),
                    ]
                ]
            )

            await safe_edit_caption(msg, caption, keyboard)
            await asyncio.sleep(10)

        except Exception as e:
            print("[vcstats] auto-refresh loop error:", e)
            break


# =============================================================
# STOP AUTO REFRESH
# =============================================================
@app.on_callback_query(filters.regex("^vc_stop_autorefresh$"))
async def stop_autorefresh(client, cq: CallbackQuery):
    await cq.answer("🛑 Stopped", show_alert=True)


# =============================================================
# AUDIO CHAT PAGINATION
# =============================================================
@app.on_callback_query(filters.regex("^vc_audio_page_"))
async def audio_page(client, cq: CallbackQuery):

    if cq.from_user.id not in SUDOERS:
        return await cq.answer("❌ Unauthorized", show_alert=True)

    page = int(cq.data.split("_")[-1])

    audio, _ = await get_cached_stats()
    page_items, total_pages = paginate_list(audio, page)

    text = "**🎧 Active Audio Chats**\n\n"
    if not audio:
        text += "`No active audio chats.`"
    else:
        for cid in page_items:
            text += f"• `{cid}`\n"

    buttons = []
    if page > 1:
        buttons.append(InlineKeyboardButton("⬅ Prev", callback_data=f"vc_audio_page_{page-1}"))
    if page < total_pages:
        buttons.append(InlineKeyboardButton("Next ➡", callback_data=f"vc_audio_page_{page+1}"))

    rows = []
    if buttons:
        rows.append(buttons)
    rows.append([InlineKeyboardButton("🔙 Back", callback_data="vc_refresh_manual")])

    keyboard = InlineKeyboardMarkup(rows)

    await safe_edit_caption(cq.message, text, keyboard)
    await cq.answer()


# =============================================================
# VIDEO CHAT PAGINATION
# =============================================================
@app.on_callback_query(filters.regex("^vc_video_page_"))
async def video_page(client, cq: CallbackQuery):

    if cq.from_user.id not in SUDOERS:
        return await cq.answer("❌ Unauthorized", show_alert=True)

    page = int(cq.data.split("_")[-1])

    _, video = await get_cached_stats()
    page_items, total_pages = paginate_list(video, page)

    text = "**🎥 Active Video Chats**\n\n"
    if not video:
        text += "`No active video chats.`"
    else:
        for cid in page_items:
            text += f"• `{cid}`\n"

    buttons = []
    if page > 1:
        buttons.append(InlineKeyboardButton("⬅ Prev", callback_data=f"vc_video_page_{page-1}"))
    if page < total_pages:
        buttons.append(InlineKeyboardButton("Next ➡", callback_data=f"vc_video_page_{page+1}"))

    rows = []
    if buttons:
        rows.append(buttons)
    rows.append([InlineKeyboardButton("🔙 Back", callback_data="vc_refresh_manual")])

    keyboard = InlineKeyboardMarkup(rows)

    await safe_edit_caption(cq.message, text, keyboard)
    await cq.answer()


# =============================================================
# CLOSE BUTTON
# =============================================================
@app.on_callback_query(filters.regex("^vc_close$"))
async def vc_close(client, cq: CallbackQuery):
    try:
        await cq.message.delete()
    except:
        pass
    await cq.answer("❌ Closed")
