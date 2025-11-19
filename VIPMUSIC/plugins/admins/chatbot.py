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

# Import client
try:
    from main import app
except:
    from VIPMUSIC import app

# MongoDB
try:
    from config import MONGO_URL
except:
    MONGO_URL = os.environ.get("MONGO_URL", "mongodb+srv://iamnobita1:nobitamusic1@cluster0.k08op.mongodb.net/?retryWrites=true&w=majority")

mongo = MongoClient(MONGO_URL)
db = mongo["ghosttchat"]
chatai_coll = db["chatai"]
status_coll = db["chatbot_status"]
lang_coll = db["chat_langs"]

translator = GoogleTranslator()

# Runtime caches
replies_cache = []
blocklist = {}
message_counts = {}


# ===================== Utility ===================== #

async def load_replies_cache():
    global replies_cache
    try:
        replies_cache = list(chatai_coll.find({}))
    except:
        replies_cache = []


def get_reply(word: str):
    global replies_cache

    # reload cache if empty
    if not replies_cache:
        try:
            replies_cache = list(chatai_coll.find({}))
        except:
            pass

    if not replies_cache:
        return None

    exact = [r for r in replies_cache if r["word"] == word]
    chosen = exact if exact else replies_cache

    return random.choice(chosen)


def is_admin(client, chat_id, user_id):
    try:
        m = client.get_chat_member(chat_id, user_id)
        return m.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except:
        return False


async def save_reply(bot_msg: Message, user_msg: Message):
    try:
        if not bot_msg.text:
            return

        reply_data = {
            "word": bot_msg.text,
            "text": None,
            "check": "none",
        }

        if user_msg.sticker:
            reply_data["text"] = user_msg.sticker.file_id
            reply_data["check"] = "sticker"
        elif user_msg.photo:
            reply_data["text"] = user_msg.photo.file_id
            reply_data["check"] = "photo"
        elif user_msg.video:
            reply_data["text"] = user_msg.video.file_id
            reply_data["check"] = "video"
        elif user_msg.audio:
            reply_data["text"] = user_msg.audio.file_id
            reply_data["check"] = "audio"
        elif user_msg.animation:
            reply_data["text"] = user_msg.animation.file_id
            reply_data["check"] = "gif"
        elif user_msg.voice:
            reply_data["text"] = user_msg.voice.file_id
            reply_data["check"] = "voice"
        elif user_msg.text:
            reply_data["text"] = user_msg.text
            reply_data["check"] = "none"
        else:
            return

        # Avoid duplicates
        if not chatai_coll.find_one(reply_data):
            chatai_coll.insert_one(reply_data)
            replies_cache.append(reply_data)

    except Exception as e:
        print("[chatbot] save_reply error:", e)


async def get_chat_lang(chat_id):
    doc = lang_coll.find_one({"chat_id": chat_id})
    return doc["language"] if doc and "language" in doc else None


# ===================== INLINE KEYBOARD ===================== #

def toggle_kb(enabled: bool):
    if enabled:
        return InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔴 Disable", callback_data="cb_disable")]]
        )
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🟢 Enable", callback_data="cb_enable")]]
    )


# ===================== COMMAND: /chatbot ===================== #

@app.on_message(filters.command("chatbot") & filters.group)
async def chatbot_group_cmd(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if not is_admin(client, chat_id, user_id):
        return await message.reply_text("❌ Only admins can manage chatbot settings.")

    s = status_coll.find_one({"chat_id": chat_id})
    enabled = not s or s.get("status") == "enabled"

    txt = (
        "**🤖 Chatbot Settings**\n\n"
        f"Status: **{'🟢 Enabled' if enabled else '🔴 Disabled'}**\n\n"
        "Use the buttons below to toggle."
    )

    await message.reply_text(txt, reply_markup=toggle_kb(enabled))


@app.on_message(filters.command("chatbot") & filters.private)
async def chatbot_private_cmd(client, message: Message):
    chat_id = message.chat.id
    s = status_coll.find_one({"chat_id": chat_id})
    enabled = not s or s.get("status") == "enabled"
    txt = (
        "**🤖 Chatbot (Private)**\n\n"
        f"Status: **{'🟢 Enabled' if enabled else '🔴 Disabled'}**"
    )
    await message.reply_text(txt, reply_markup=toggle_kb(enabled))


# ===================== CALLBACKS ===================== #

@app.on_callback_query(filters.regex("^cb_"))
async def chatbot_cb(client, cq: CallbackQuery):
    chat_id = cq.message.chat.id
    user_id = cq.from_user.id

    # Check admin in group
    if cq.message.chat.type in ("group", "supergroup"):
        if not is_admin(client, chat_id, user_id):
            return await cq.answer("Admins only!", show_alert=True)

    if cq.data == "cb_enable":
        status_coll.update_one(
            {"chat_id": chat_id}, {"$set": {"status": "enabled"}}, upsert=True
        )
        await cq.message.edit_text(
            "**🤖 Chatbot Enabled!**",
            reply_markup=toggle_kb(True)
        )
        await cq.answer("Enabled.")
    else:
        status_coll.update_one(
            {"chat_id": chat_id}, {"$set": {"status": "disabled"}}, upsert=True
        )
        await cq.message.edit_text(
            "**🤖 Chatbot Disabled!**",
            reply_markup=toggle_kb(False)
        )
        await cq.answer("Disabled.")


# ===================== SET LANGUAGE ===================== #

@app.on_message(filters.command("setlang") & filters.group)
async def setlang_group(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if not is_admin(client, chat_id, user_id):
        return await message.reply_text("❌ Only admins can set language.")

    if len(message.command) < 2:
        return await message.reply_text("Usage: /setlang <code>")

    lang = message.command[1]
    lang_coll.update_one({"chat_id": chat_id}, {"$set": {"language": lang}}, upsert=True)
    await message.reply_text(f"✅ Language set to `{lang}`")


@app.on_message(filters.command("setlang") & filters.private)
async def setlang_private(client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: /setlang <code>")

    lang = message.command[1]
    lang_coll.update_one({"chat_id": message.chat.id}, {"$set": {"language": lang}}, upsert=True)
    await message.reply_text(f"✅ Language set to `{lang}`")


# ===================== MAIN CHATBOT RESPONSE ===================== #

@app.on_message(filters.incoming)
async def chatbot_handler(client, message: Message):
    # Ignore edited messages safely
    if message.edit_date:
        return

    global blocklist, message_counts

    if not message.from_user:
        return

    user_id = message.from_user.id
    chat_id = message.chat.id
    now = datetime.utcnow()

    # Cleanup expired blocks
    blocklist = {u: t for u, t in blocklist.items() if t > now}

    # Rate-limit
    mc = message_counts.get(user_id)
    if not mc:
        message_counts[user_id] = {"count": 1, "last_time": now}
    else:
        diff = (now - mc["last_time"]).total_seconds()
        mc["count"] = mc["count"] + 1 if diff <= 3 else 1
        mc["last_time"] = now

        if mc["count"] >= 6:
            blocklist[user_id] = now + timedelta(minutes=1)
            message_counts.pop(user_id, None)
            try:
                await message.reply_text("⛔ You are blocked for 1 minute due to spam.")
            except:
                pass
            return

    if user_id in blocklist:
        return

    # Respect enable/disable
    s = status_coll.find_one({"chat_id": chat_id})
    if s and s.get("status") == "disabled":
        return

    # Ignore commands
    if message.text and message.text.startswith(("/", "!", ".", "@", "#", "?")):
        return

    # Decide if bot should respond
    should_answer = False
    if message.reply_to_message:
        if getattr(message.reply_to_message, "from_user", None) and message.reply_to_message.from_user.id == client.me.id:
            should_answer = True
    else:
        should_answer = True  # Change this to False if you only want reply-based chatting

    # Respond
    if should_answer:
        r = get_reply(message.text or "")
        if r:
            response = r["text"]
            kind = r["check"]
            lang = await get_chat_lang(chat_id)

            # Translate text
            if kind == "none" and response and lang and lang != "nolang":
                try:
                    response = GoogleTranslator(source="auto", target=lang).translate(response)
                except:
                    pass

            try:
                if kind == "sticker":
                    await message.reply_sticker(response)
                elif kind == "photo":
                    await message.reply_photo(response)
                elif kind == "video":
                    await message.reply_video(response)
                elif kind == "audio":
                    await message.reply_audio(response)
                elif kind == "gif":
                    await message.reply_animation(response)
                elif kind == "voice":
                    await message.reply_voice(response)
                else:
                    await message.reply_text(response)
            except:
                try:
                    await message.reply_text(response)
                except:
                    pass
        else:
            try:
                await message.reply_text("I don't understand. 🤔")
            except:
                pass

    # Learning
    if message.reply_to_message:
        if getattr(message.reply_to_message, "from_user", None) and message.reply_to_message.from_user.id == client.me.id:
            await save_reply(message.reply_to_message, message)
