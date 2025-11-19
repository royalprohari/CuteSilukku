"""
chatbot.py  — Combined chatbot + toggle + admin tools plugin for HB-Cute / VIPMUSIC

Features:
- Auto-reply using learned mappings (word -> reply)
- Learns when users reply to the bot (saves bot_message -> user_reply)
- Spam protection per-user
- /chatbot command with inline Enable / Disable buttons (admin-only in groups)
- /chatbot reset   -> clears chat-specific learned replies (admin-only)
- /setlang <lang>  -> set per-chat language (admin-only). Use language code like 'en', 'hi', etc.
- Uses MongoDB collections: chatai, chatbot_status, chat_langs

Install:
pip install pymongo deep-translator
Ensure MONGO_URL is in config.py or environment.
"""

import os
import random
from datetime import datetime, timedelta

from pyrogram import filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from pyrogram.errors import MessageEmpty
from pyrogram.enums import ChatMemberStatus

from pymongo import MongoClient
from deep_translator import GoogleTranslator

# Try to import the running app/client used in HB-Cute / VIPMUSIC.
# Adjust if your project exposes the client under a different name.
try:
    # HB-Cute / VIPMUSIC often exposes app in VIPMUSIC package
    from VIPMUSIC import app
except Exception:
    try:
        # fallback to main.py style
        from main import app
    except Exception:
        raise RuntimeError("Could not import 'app'. Ensure your bot exposes the pyrogram Client as 'app'.")

# Load MONGO_URL from repo config or environment
try:
    from config import MONGO_URL
except Exception:
    MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")

# Mongo setup
mongo = MongoClient(MONGO_URL)
db = mongo.get_database("vipmusic_db")
chatai_coll = db.get_collection("chatai")
status_coll = db.get_collection("chatbot_status")
lang_coll = db.get_collection("chat_langs")

# Translator (used when /setlang is set)
translator = GoogleTranslator()

# runtime caches and rate limiting
replies_cache = []     # list of dicts from DB
blocklist = {}         # user_id -> unblock_datetime
message_counts = {}    # user_id -> {"count": int, "last_time": datetime}


# ------------------------ Utility / DB helpers ------------------------ #
async def load_replies_cache():
    """Load all mappings into memory (call once at startup / as needed)."""
    global replies_cache
    try:
        docs = list(chatai_coll.find({}))
        replies_cache = docs
    except Exception as e:
        print(f"[chatbot] load_replies_cache error: {e}")
        replies_cache = []


def get_reply_sync(word: str):
    """Return a random reply dict. If exact matches for 'word' exist, choose among them;
    otherwise pick from the whole cache. Returns None if empty."""
    global replies_cache
    if not replies_cache:
        try:
            docs = list(chatai_coll.find({}))
            replies_cache.extend(docs)
        except Exception:
            pass

    if not replies_cache:
        return None

    exact = [r for r in replies_cache if r.get("word") == (word or "")]
    candidates = exact if exact else replies_cache
    return random.choice(candidates) if candidates else None


def is_user_admin(client, chat_id: int, user_id: int) -> bool:
    """Return True if user is chat admin/owner (works for groups)."""
    try:
        member = client.get_chat_member(chat_id, user_id)
        return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except Exception:
        return False


async def save_reply(original_message: Message, reply_message: Message):
    """
    Save mapping original_message.text -> reply_message content (file_id or text).
    Avoid duplicates. Only saves when original_message has text (word).
    """
    try:
        if not original_message or not getattr(original_message, "text", None):
            return

        reply_data = {
            "word": original_message.text,
            "text": None,
            "check": "none",
            "created_at": datetime.utcnow(),
        }

        if getattr(reply_message, "sticker", None):
            reply_data["text"] = reply_message.sticker.file_id
            reply_data["check"] = "sticker"
        elif getattr(reply_message, "photo", None):
            # photo is an array -> file_id property on PhotoSize is accessible directly as .file_id
            reply_data["text"] = reply_message.photo.file_id
            reply_data["check"] = "photo"
        elif getattr(reply_message, "video", None):
            reply_data["text"] = reply_message.video.file_id
            reply_data["check"] = "video"
        elif getattr(reply_message, "audio", None):
            reply_data["text"] = reply_message.audio.file_id
            reply_data["check"] = "audio"
        elif getattr(reply_message, "animation", None):
            reply_data["text"] = reply_message.animation.file_id
            reply_data["check"] = "gif"
        elif getattr(reply_message, "voice", None):
            reply_data["text"] = reply_message.voice.file_id
            reply_data["check"] = "voice"
        elif getattr(reply_message, "text", None):
            reply_data["text"] = reply_message.text
            reply_data["check"] = "none"
        else:
            # unsupported reply type
            return

        # dedupe by identical mapping
        exists = chatai_coll.find_one(
            {"word": reply_data["word"], "text": reply_data["text"], "check": reply_data["check"]}
        )
        if not exists:
            chatai_coll.insert_one(reply_data)
            replies_cache.append(reply_data)

    except Exception as e:
        print(f"[chatbot] save_reply error: {e}")


async def get_chat_language(chat_id: int):
    doc = lang_coll.find_one({"chat_id": chat_id})
    if doc and "language" in doc:
        return doc["language"]
    return None


# ------------------------ Commands & Callbacks ------------------------ #

# Inline keyboard helper
def chatbot_keyboard(is_enabled: bool):
    if is_enabled:
        return InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔴 Disable", callback_data="cb_disable")]]
        )
    else:
        return InlineKeyboardMarkup(
            [[InlineKeyboardButton("🟢 Enable", callback_data="cb_enable")]]
        )


# show settings (group) — only admins can use
@app.on_message(filters.command("chatbot") & filters.group)
async def chatbot_cmd(client, message: Message):
    """Show chatbot status with inline enable/disable. Only admins can toggle via buttons."""
    chat_id = message.chat.id
    user_id = message.from_user.id

    # check admin in group
    if not is_user_admin(client, chat_id, user_id):
        return await message.reply_text("❌ Only group admins can configure the chatbot.")

    status_doc = status_coll.find_one({"chat_id": chat_id})
    is_enabled = not status_doc or status_doc.get("status") == "enabled"

    text = (
        "**🤖 Chatbot Settings**\n\n"
        f"Current Status: **{'🟢 Enabled' if is_enabled else '🔴 Disabled'}**\n\n"
        "Use the buttons below to toggle the chatbot for this chat.\n\n"
        "Admin-only: Only group admins can change this."
    )

    await message.reply_text(text, reply_markup=chatbot_keyboard(is_enabled))


# callbacks for enable/disable
@app.on_callback_query(filters.regex("^cb_enable$") | filters.regex("^cb_disable$"))
async def chatbot_toggle_cb(client, cq: CallbackQuery):
    """Handle enable/disable button presses. Confirm caller is admin in group."""
    try:
        chat_id = cq.message.chat.id
        caller_id = cq.from_user.id

        # Only allow admins to toggle in groups
        if cq.message.chat.type in ("group",):  # 'group' covers both group/supergroup in v2
            if not is_user_admin(client, chat_id, caller_id):
                await cq.answer("Only group admins can perform this action.", show_alert=True)
                return

        if cq.data == "cb_enable":
            status_coll.update_one({"chat_id": chat_id}, {"$set": {"status": "enabled"}}, upsert=True)
            await cq.message.edit_text(
                "**🤖 Chatbot Enabled Successfully!**\n\nStatus: **🟢 Enabled**",
                reply_markup=chatbot_keyboard(True),
            )
            await cq.answer("Chatbot enabled.")
        else:
            status_coll.update_one({"chat_id": chat_id}, {"$set": {"status": "disabled"}}, upsert=True)
            await cq.message.edit_text(
                "**🤖 Chatbot Disabled Successfully!**\n\nStatus: **🔴 Disabled**",
                reply_markup=chatbot_keyboard(False),
            )
            await cq.answer("Chatbot disabled.")
    except Exception as e:
        print(f"[chatbot] toggle cb error: {e}")
        try:
            await cq.answer("An error occurred.", show_alert=True)
        except Exception:
            pass


# show settings in private (owner/user)
@app.on_message(filters.command("chatbot") & filters.private)
async def chatbot_cmd_private(client, message: Message):
    """If used in private chat, show status and allow toggle (owner or user)."""
    chat_id = message.chat.id
    status_doc = status_coll.find_one({"chat_id": chat_id})
    is_enabled = not status_doc or status_doc.get("status") == "enabled"

    text = (
        "**🤖 Chatbot (Private Chat)**\n\n"
        f"Current Status: **{'🟢 Enabled' if is_enabled else '🔴 Disabled'}**\n\n"
        "Use the buttons below to toggle the chatbot for this chat."
    )
    await message.reply_text(text, reply_markup=chatbot_keyboard(is_enabled))


# Admin-only: clear learned replies for this chat (global clear)
@app.on_message(filters.command("chatbot") & filters.regex(r"^/chatbot\s+reset$", flags=0) & filters.group)
async def chatbot_reset_group(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if not is_user_admin(client, chat_id, user_id):
        return await message.reply_text("❌ Only group admins can reset chatbot data.")
    chatai_coll.delete_many({})
    replies_cache.clear()
    await message.reply_text("✅ All learned replies cleared (global).")


@app.on_message(filters.command("chatbot") & filters.regex(r"^/chatbot\s+reset$", flags=0) & filters.private)
async def chatbot_reset_private(client, message: Message):
    chatai_coll.delete_many({})
    replies_cache.clear()
    await message.reply_text("✅ All learned replies cleared (global).")


# Admin-only: set per-chat language for translation of replies
@app.on_message(filters.command("setlang") & filters.group)
async def setlang_group(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if not is_user_admin(client, chat_id, user_id):
        return await message.reply_text("❌ Only group admins can set chatbot language for the chat.")
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.reply_text("Usage: /setlang <language_code>\nExample: /setlang en  or  /setlang hi")
    lang = args[1].strip()
    lang_coll.update_one({"chat_id": chat_id}, {"$set": {"language": lang}}, upsert=True)
    await message.reply_text(f"✅ Chatbot language set to: `{lang}`")


@app.on_message(filters.command("setlang") & filters.private)
async def setlang_private(client, message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return await message.reply_text("Usage: /setlang <language_code>")
    lang = args[1].strip()
    chat_id = message.chat.id
    lang_coll.update_one({"chat_id": chat_id}, {"$set": {"language": lang}}, upsert=True)
    await message.reply_text(f"✅ Chatbot language set to: `{lang}`")


# ------------------------ Main Chatbot Handler ------------------------ #

@app.on_message(filters.incoming & ~filters.edited)
async def chatbot_handler(client, message: Message):
    """
    Main runtime:
    - rate limits spammers
    - respects per-chat enabled/disabled status
    - responds using learned replies (media/text)
    - saves user replies when replying to the bot (learns)
    """
    global blocklist, message_counts

    try:
        if not message.from_user:
            return

        user_id = message.from_user.id
        chat_id = message.chat.id
        now = datetime.utcnow()

        # Cleanup expired blocks
        blocklist = {u: t for u, t in blocklist.items() if t > now}

        # Spam protection
        mc = message_counts.get(user_id)
        if not mc:
            message_counts[user_id] = {"count": 1, "last_time": now}
        else:
            diff = (now - mc["last_time"]).total_seconds()
            if diff <= 3:
                mc["count"] += 1
            else:
                mc["count"] = 1
            mc["last_time"] = now

            if mc["count"] >= 6:
                blocklist[user_id] = now + timedelta(minutes=1)
                message_counts.pop(user_id, None)
                try:
                    await message.reply_text(
                        f"**Hey, {message.from_user.first_name}**\n\n"
                        "**You are blocked for 1 minute due to spam messages.**"
                    )
                except Exception:
                    pass
                return

        if user_id in blocklist:
            return

        # Respect enabled/disabled
        status_doc = status_coll.find_one({"chat_id": chat_id})
        if status_doc and status_doc.get("status") == "disabled":
            return

        # ignore commands
        if getattr(message, "text", None) and any(message.text.startswith(p) for p in ["/", "!", ".", "?", "#", "@"]):
            return

        # Bot should reply if message is a reply to the bot OR freely respond to chat (adjustable)
        should_respond = False
        if getattr(message, "reply_to_message", None) and getattr(message.reply_to_message, "from_user", None):
            # if user's message is replying to bot
            try:
                bot_id = client.get_me().id
            except Exception:
                bot_id = None
            if bot_id and message.reply_to_message.from_user.id == bot_id:
                should_respond = True
        else:
            # Allow general chat responses; set False to only respond when explicitly replied to
            should_respond = True

        if should_respond:
            reply_data = get_reply_sync(message.text or "")
            if reply_data:
                response_text = reply_data.get("text") or ""
                kind = reply_data.get("check", "none")
                chat_lang = await get_chat_language(chat_id)

                # translate textual replies when language set
                if kind == "none" and response_text:
                    if chat_lang and chat_lang != "nolang":
                        try:
                            translated = GoogleTranslator(source="auto", target=chat_lang).translate(response_text)
                            if translated:
                                response_text = translated
                        except Exception:
                            # on error, fall back to original
                            pass

                # send appropriate type
                try:
                    if kind == "sticker":
                        await message.reply_sticker(response_text)
                    elif kind == "photo":
                        await message.reply_photo(response_text)
                    elif kind == "video":
                        await message.reply_video(response_text)
                    elif kind == "audio":
                        await message.reply_audio(response_text)
                    elif kind == "gif":
                        await message.reply_animation(response_text)
                    elif kind == "voice":
                        await message.reply_voice(response_text)
                    else:
                        await message.reply_text(response_text or "I don't understand.")
                except MessageEmpty:
                    pass
                except Exception as e:
                    # fallback to text
                    try:
                        await message.reply_text(response_text or "I don't understand.")
                    except Exception:
                        print(f"[chatbot] send error: {e}")
            else:
                # no learned reply
                try:
                    await message.reply_text("**I don't understand. What are you saying?**")
                except Exception:
                    pass

        # Learning: if user replied to bot's message, save mapping bot_message -> user's reply
        if getattr(message, "reply_to_message", None) and getattr(message.reply_to_message, "from_user", None):
            try:
                bot_id = client.get_me().id
            except Exception:
                bot_id = None
            if bot_id and message.reply_to_message.from_user.id == bot_id:
                await save_reply(message.reply_to_message, message)

    except Exception as e:
        print(f"[chatbot] handler exception: {e}")
