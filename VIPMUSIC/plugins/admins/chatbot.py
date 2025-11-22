import os, random, re
from datetime import datetime, timedelta
from typing import Optional
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ChatMemberStatus
from pymongo import MongoClient
from deep_translator import GoogleTranslator

# Application client
try:
    from VIPMUSIC import app
except:
    try:
        from main import app
    except:
        raise RuntimeError("Pyrogram Client not found as 'app'")

# MongoDB
try:
    from config import MONGO_URL
except:
    MONGO_URL = os.environ.get("MONGO_URL",
        "mongodb+srv://iamnobita1:nobitamusic1@cluster0.k08op.mongodb.net/?retryWrites=true&w=majority"
    )

mongo = MongoClient(MONGO_URL)
db = mongo.get_database("vipmusic_db")
chatai_coll = db.get_collection("chatai")
status_coll = db.get_collection("chatbot_status")
lang_coll = db.get_collection("chat_langs")
block_coll = db.get_collection("chatbot_blocklist")

translator = GoogleTranslator()

# Runtime caches & counters
replies_cache = []
blocklist = {}
message_counts = {}
global_blocked_patterns = []

# Loaders
def load_replies_cache():
    global replies_cache
    try:
        replies_cache = list(chatai_coll.find({}))
    except:
        replies_cache = []

def load_blocklist():
    global global_blocked_patterns
    global_blocked_patterns = []
    try:
        for d in block_coll.find({}):
            p = d.get("pattern") or d.get("word")
            if not p: continue
            try:
                global_blocked_patterns.append(re.compile(p, re.IGNORECASE))
            except:
                try:
                    global_blocked_patterns.append(re.compile(re.escape(p), re.IGNORECASE))
                except:
                    pass
    except:
        global_blocked_patterns = []

load_replies_cache(); load_blocklist()

# Small helpers
def _photo_file_id(msg: Message) -> Optional[str]:
    try:
        photo = getattr(msg, "photo", None)
        if not photo: return None
        if hasattr(photo, "file_id"): return photo.file_id
        if isinstance(photo, (list, tuple)) and len(photo) > 0: return photo[-1].file_id
    except: pass
    return None

def get_reply_sync(word: str):
    global replies_cache
    if not replies_cache:
        try: replies_cache = list(chatai_coll.find({}))
        except: replies_cache = []
    if not replies_cache: return None
    exact = [r for r in replies_cache if r.get("word") == (word or "")]
    candidates = exact if exact else replies_cache
    return random.choice(candidates) if candidates else None

async def is_user_admin(client, chat_id: int, user_id: int) -> bool:
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except:
        return False

async def save_reply(original: Message, reply: Message):
    try:
        if not original or not original.text: return
        data = {"word": original.text, "text": None, "kind": "text", "created_at": datetime.utcnow()}
        if reply.sticker:
            data["text"] = reply.sticker.file_id; data["kind"] = "sticker"
        elif _photo_file_id(reply):
            data["text"] = _photo_file_id(reply); data["kind"] = "photo"
        elif reply.video:
            data["text"] = reply.video.file_id; data["kind"] = "video"
        elif reply.audio:
            data["text"] = reply.audio.file_id; data["kind"] = "audio"
        elif reply.animation:
            data["text"] = reply.animation.file_id; data["kind"] = "gif"
        elif reply.voice:
            data["text"] = reply.voice.file_id; data["kind"] = "voice"
        elif reply.text:
            data["text"] = reply.text; data["kind"] = "text"
        else:
            return
        exists = chatai_coll.find_one({"word": data["word"], "text": data["text"], "kind": data["kind"]})
        if not exists:
            chatai_coll.insert_one(data); replies_cache.append(data)
    except Exception as e:
        print("[chatbot] save_reply:", e)

async def get_chat_language(chat_id: int) -> Optional[str]:
    doc = lang_coll.find_one({"chat_id": chat_id})
    return doc["language"] if doc and "language" in doc else None

def chatbot_keyboard(is_enabled: bool):
    if is_enabled:
        return InlineKeyboardMarkup([[InlineKeyboardButton("🔴 Disable", callback_data="cb_disable")]])
    return InlineKeyboardMarkup([[InlineKeyboardButton("🟢 Enable", callback_data="cb_enable")]])
# /chatbot (group)
@app.on_message(filters.command("chatbot") & filters.group)
async def chatbot_settings_group(client, message):
    chat_id = message.chat.id; user_id = message.from_user.id
    if not await is_user_admin(client, chat_id, user_id):
        return await message.reply_text("❌ Only admins can manage chatbot settings.")
    doc = status_coll.find_one({"chat_id": chat_id})
    enabled = not doc or doc.get("status") == "enabled"
    txt = "**🤖 Chatbot Settings**\n\n" + f"Current Status: **{'🟢 Enabled' if enabled else '🔴 Disabled'}**\n"
    await message.reply_text(txt, reply_markup=chatbot_keyboard(enabled))

# /chatbot (private) - show status only (no auto-reply)
@app.on_message(filters.command("chatbot") & filters.private)
async def chatbot_settings_private(client, message):
    chat_id = message.chat.id
    doc = status_coll.find_one({"chat_id": chat_id})
    enabled = not doc or doc.get("status") == "enabled"
    txt = f"**🤖 Chatbot (private)**\nStatus: **{'🟢 Enabled' if enabled else '🔴 Disabled'}**"
    await message.reply_text(txt, reply_markup=chatbot_keyboard(enabled))

# callback toggle
@app.on_callback_query(filters.regex("^cb_(enable|disable)$"))
async def chatbot_toggle_cb(client, cq: CallbackQuery):
    chat_id = cq.message.chat.id; uid = cq.from_user.id
    if cq.message.chat.type in ("group","supergroup"):
        if not await is_user_admin(client, chat_id, uid):
            return await cq.answer("Only admins can do this.", show_alert=True)
    if cq.data == "cb_enable":
        status_coll.update_one({"chat_id": chat_id}, {"$set": {"status": "enabled"}}, upsert=True)
        await cq.message.edit_text("**🤖 Chatbot Enabled!**", reply_markup=chatbot_keyboard(True)); await cq.answer("Enabled")
    else:
        status_coll.update_one({"chat_id": chat_id}, {"$set": {"status": "disabled"}}, upsert=True)
        await cq.message.edit_text("**🤖 Chatbot Disabled!**", reply_markup=chatbot_keyboard(False)); await cq.answer("Disabled")

# /chatbot reset (group only) - robust check
@app.on_message(filters.command("chatbot") & filters.group)
async def chatbot_reset_group_handler(client, message):
    text = (message.text or "").lower()
    if "reset" not in text: return
    if not await is_user_admin(client, message.chat.id, message.from_user.id):
        return await message.reply_text("❌ Only admins can do this.")
    chatai_coll.delete_many({}); replies_cache.clear()
    await message.reply_text("✅ All replies cleared.")

# /chatbot reset (private) - allow SUDO or owner usage
@app.on_message(filters.command("chatbot") & filters.private)
async def chatbot_reset_private_handler(client, message):
    text = (message.text or "").lower()
    if "reset" not in text: return
    chatai_coll.delete_many({}); replies_cache.clear()
    await message.reply_text("✅ All replies cleared.")

# /setlang (group)
@app.on_message(filters.command("setlang") & filters.group)
async def setlang_group(client, message):
    if not await is_user_admin(client, message.chat.id, message.from_user.id):
        return await message.reply_text("❌ Only admins can do this.")
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2: return await message.reply_text("Usage: /setlang <code>")
    lang = parts[1].strip()
    lang_coll.update_one({"chat_id": message.chat.id}, {"$set": {"language": lang}}, upsert=True)
    await message.reply_text(f"✅ Language set to `{lang}`")

# /setlang (private)
@app.on_message(filters.command("setlang") & filters.private)
async def setlang_private(client, message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2: return await message.reply_text("Usage: /setlang <code>")
    lang = parts[1].strip()
    lang_coll.update_one({"chat_id": message.chat.id}, {"$set": {"language": lang}}, upsert=True)
    await message.reply_text(f"✅ Language set to `{lang}`")

# Learn replies - GROUP only (bot must be the replied-to user)
@app.on_message(filters.reply & filters.group)
async def learn_reply_group(client, message):
    if not message.reply_to_message: return
    bot = await client.get_me()
    if message.reply_to_message.from_user and message.reply_to_message.from_user.id == bot.id:
        await save_reply(message.reply_to_message, message)
# SUDO list
from VIPMUSIC.misc import SUDOERS
def is_sudo(uid): return uid in SUDOERS

# /addblock <regex>
@app.on_message(filters.command("addblock"))
async def add_block_cmd(client, message):
    if not is_sudo(message.from_user.id): return await message.reply_text("❌ Only SUDO can use this command.")
    parts = message.text.split(None,1)
    if len(parts) < 2: return await message.reply_text("Usage: /addblock <regex-pattern>")
    pattern = parts[1].strip()
    # validate pattern by trying to compile
    try:
        re.compile(pattern)
    except re.error as e:
        return await message.reply_text(f"❌ Invalid regex: `{e}`")
    block_coll.update_one({"pattern": pattern}, {"$set": {"pattern": pattern}}, upsert=True)
    load_blocklist()
    await message.reply_text(f"✅ Added regex block: `{pattern}`")

# /rmblock and /removeblock aliases
@app.on_message(filters.command("rmblock") | filters.command("removeblock"))
async def rm_block_cmd(client, message):
    if not is_sudo(message.from_user.id): return await message.reply_text("❌ Only SUDO can use this command.")
    parts = message.text.split(None,1)
    if len(parts) < 2: return await message.reply_text("Usage: /rmblock <regex-pattern> or /removeblock <regex-pattern>")
    pattern = parts[1].strip()
    block_coll.delete_one({"pattern": pattern})
    load_blocklist()
    await message.reply_text(f"🗑️ Removed regex block: `{pattern}`")

# /listblock
@app.on_message(filters.command("listblock"))
async def list_block_cmd(client, message):
    if not is_sudo(message.from_user.id): return await message.reply_text("❌ Only SUDO can use this command.")
    docs = list(block_coll.find({}))
    if not docs: return await message.reply_text("📭 No blocked patterns.")
    txt = "**🔐 Regex Blocklist:**\n\n" + "\n".join(f"• `{d.get('pattern')}`" for d in docs)
    await message.reply_text(txt)

# Utility: check if text is blocked by any pattern (safe fallback included)
def bot_reply_blocked(text: str) -> bool:
    if not text: return False
    for pat in global_blocked_patterns:
        try:
            if pat.search(text):
                return True
        except Exception:
            try:
                if re.search(pat.pattern if hasattr(pat,'pattern') else str(pat), text, flags=re.IGNORECASE):
                    return True
            except:
                pass
    return False
# Main chatbot handler - GROUPS only. This disables auto-replies in private chats.
@app.on_message(filters.group & filters.incoming & ~filters.me, group=99)
async def chatbot_handler(client, message: Message):
    if message.edit_date: return
    if not message.from_user: return

    user_id = message.from_user.id
    chat_id = message.chat.id
    now = datetime.utcnow()

    global blocklist, message_counts
    blocklist = {u: t for u, t in blocklist.items() if t > now}

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
            try: await message.reply_text("⛔ Blocked 1 minute for spam.")
            except: pass
            return

    if user_id in blocklist: return

    s = status_coll.find_one({"chat_id": chat_id})
    if s and s.get("status") == "disabled": return

    # allow commands like /play /start /help etc.
    if message.text and message.text.startswith("/"): return

    # determine whether bot should respond
    should = False
    if message.reply_to_message:
        bot = await client.get_me()
        if message.reply_to_message.from_user and message.reply_to_message.from_user.id == bot.id:
            should = True
    else:
        should = True
    if not should: return

    r = get_reply_sync(message.text or "")
    if not r:
        try: await message.reply_text("I don't understand. 🤔")
        except: pass
        return

    response = r.get("text", "")
    kind = r.get("kind", "text")

    # language translation (apply and then block-check on final text to prevent slipping)
    lang = await get_chat_language(chat_id)
    final_text = response
    if kind == "text" and response and lang and lang != "nolang":
        try: final_text = translator.translate(response, target=lang)
        except: final_text = response

    # caption handling if present in record
    caption = None
    if isinstance(r, dict):
        caption = r.get("caption") if isinstance(r.get("caption"), str) else None
    final_caption = None
    if caption:
        final_caption = caption
        if lang and lang != "nolang":
            try: final_caption = translator.translate(caption, target=lang)
            except: final_caption = caption

    # Block checks BEFORE sending
    if kind == "text":
        if bot_reply_blocked(final_text):
            return
    else:
        if (final_caption and bot_reply_blocked(final_caption)) or (response and bot_reply_blocked(response)):
            return

    # Safe send
    try:
        if kind == "sticker":
            if bot_reply_blocked(response): return
            await message.reply_sticker(response)
        elif kind == "photo":
            if final_caption and bot_reply_blocked(final_caption): return
            if final_caption: await message.reply_photo(response, caption=final_caption)
            else: await message.reply_photo(response)
        elif kind == "video":
            if final_caption and bot_reply_blocked(final_caption): return
            if final_caption: await message.reply_video(response, caption=final_caption)
            else: await message.reply_video(response)
        elif kind == "audio":
            if final_caption and bot_reply_blocked(final_caption): return
            if final_caption: await message.reply_audio(response, caption=final_caption)
            else: await message.reply_audio(response)
        elif kind == "gif":
            if final_caption and bot_reply_blocked(final_caption): return
            if final_caption: await message.reply_animation(response, caption=final_caption)
            else: await message.reply_animation(response)
        elif kind == "voice":
            if bot_reply_blocked(response): return
            await message.reply_voice(response)
        else:
            if bot_reply_blocked(final_text): return
            await message.reply_text(final_text or "I don't understand.")
    except Exception:
        try:
            if kind != "text" and response and not bot_reply_blocked(response):
                await message.reply_text(response)
            else:
                await message.reply_text("I don't understand.")
        except:
            pass
