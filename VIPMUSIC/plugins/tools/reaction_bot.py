import asyncio
import random
from typing import Set, Tuple, Optional, Dict

from pyrogram import filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)
from pyrogram.enums import ChatMemberStatus

from VIPMUSIC import app
from config import BANNED_USERS, START_REACTIONS, OWNER_ID
from VIPMUSIC.utils.database import mongodb, get_sudoers

print("[reaction] loaded")


# ============================================================
# DATABASE
# ============================================================
COLLECTION = mongodb["reaction_mentions"]
SETTINGS = mongodb["reaction_settings"]


# ============================================================
# STATE / CACHE
# ============================================================
REACTION_ENABLED = True
custom_mentions: Set[str] = set()

VALID_REACTIONS = {
    "❤️", "💖", "💘", "💞", "💓", "✨", "🔥", "💫",
    "💥", "🌸", "😍", "🥰", "💎", "🌙", "🌹", "😂",
    "😎", "🤩", "😘", "😉", "🤭", "💐", "😻", "🥳"
}

SAFE_REACTIONS = [x for x in START_REACTIONS if x in VALID_REACTIONS]
if not SAFE_REACTIONS:
    SAFE_REACTIONS = list(VALID_REACTIONS)

chat_used_reactions: Dict[int, Set[str]] = {}


# ============================================================
# HELPER FUNCTIONS
# ============================================================
def next_emoji(chat_id: int) -> str:
    """Returns a non-repeating emoji per chat."""
    if chat_id not in chat_used_reactions:
        chat_used_reactions[chat_id] = set()

    used = chat_used_reactions[chat_id]

    if len(used) >= len(SAFE_REACTIONS):
        used.clear()

    remaining = [e for e in SAFE_REACTIONS if e not in used]
    emoji = random.choice(remaining)
    used.add(emoji)
    chat_used_reactions[chat_id] = used
    return emoji


async def load_custom_mentions():
    """Loads custom reaction triggers from DB."""
    try:
        docs = await COLLECTION.find().to_list(None)
        for doc in docs:
            name = str(doc.get("name")).lower().lstrip("@")
            custom_mentions.add(name)
        print(f"[Reaction] Loaded {len(custom_mentions)} custom triggers.")
    except Exception as e:
        print("[Reaction] DB Error:", e)


async def load_reaction_state():
    """Loads ON/OFF switch from DB."""
    global REACTION_ENABLED
    doc = await SETTINGS.find_one({"_id": "switch"})
    REACTION_ENABLED = doc.get("enabled", True) if doc else True
    print(f"[Reaction Switch] Loaded: {REACTION_ENABLED}")


asyncio.get_event_loop().create_task(load_custom_mentions())
asyncio.get_event_loop().create_task(load_reaction_state())


# ============================================================
# ADMIN CHECK
# ============================================================
async def is_admin_or_sudo(client, message: Message):
    """Fixes admin detection for Telegram groups."""
    user_id = message.from_user.id
    chat_id = message.chat.id

    sudo = await get_sudoers()
    if user_id == OWNER_ID or user_id in sudo:
        return True

    try:
        mem = await client.get_chat_member(chat_id, user_id)
        return mem.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except:
        return False


# ============================================================
# /REACTION COMMAND
# ============================================================
@app.on_message(filters.command(["reaction", "reactionon", "reactionoff"]) & ~BANNED_USERS, group=5)
async def reaction_cmd(client, message: Message):
    global REACTION_ENABLED

    if not await is_admin_or_sudo(client, message):
        return await message.reply_text("Only admins can do this.")

    cmd = message.command[0].lower()

    if cmd == "reactionon":
        REACTION_ENABLED = True
        await SETTINGS.update_one({"_id": "switch"}, {"$set": {"enabled": True}}, upsert=True)
        return await message.reply_text("🟢 **Reaction Enabled**")

    if cmd == "reactionoff":
        REACTION_ENABLED = False
        await SETTINGS.update_one({"_id": "switch"}, {"$set": {"enabled": False}}, upsert=True)
        return await message.reply_text("🔴 **Reaction Disabled**")

    # /reaction panel
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🟢 Enable", callback_data="react_on"),
                InlineKeyboardButton("🔴 Disable", callback_data="react_off"),
            ],
            [InlineKeyboardButton("ℹ️ Status", callback_data="react_status")]
        ]
    )

    await message.reply_text(
        f"**Reaction Control Panel**\n\nStatus: {'🟢 ON' if REACTION_ENABLED else '🔴 OFF'}",
        reply_markup=kb
    )


# ============================================================
# CALLBACK BUTTONS
# ============================================================
@app.on_callback_query(filters.regex("^react_"), group=5)
async def reaction_buttons(client, query: CallbackQuery):
    global REACTION_ENABLED

    if not await is_admin_or_sudo(client, query.message):
        return await query.answer("Not allowed", show_alert=True)

    act = query.data

    if act == "react_on":
        REACTION_ENABLED = True
        await SETTINGS.update_one({"_id": "switch"}, {"$set": {"enabled": True}}, upsert=True)
        return await query.edit_message_text("🟢 **Reaction Enabled**")

    if act == "react_off":
        REACTION_ENABLED = False
        await SETTINGS.update_one({"_id": "switch"}, {"$set": {"enabled": False}}, upsert=True)
        return await query.edit_message_text("🔴 **Reaction Disabled**")

    if act == "react_status":
        return await query.answer(
            f"Reactions are {'ON' if REACTION_ENABLED else 'OFF'}",
            show_alert=True
        )


# ============================================================
# AUTO REACT SYSTEM (MAIN PART)
# ============================================================
@app.on_message((filters.text | filters.caption) & ~BANNED_USERS, group=99)
async def auto_react(client, message: Message):
    """Main reaction logic."""
    if not REACTION_ENABLED:
        return

    if not message.from_user:
        return

    text = (message.text or message.caption or "").lower()

    if text.startswith("/"):
        return

    chat_id = message.chat.id

    # Auto react to ANY @username mention (default)
    entities = list(message.entities or []) + list(message.caption_entities or [])
    usernames = set()

    for e in entities:
        if e.type == "mention":
            username = (message.text or message.caption)[e.offset:e.offset + e.length]
            usernames.add(username.lstrip("@").lower())

        elif e.type == "text_mention" and e.user:
            if e.user.username:
                usernames.add(e.user.username.lower())

    # DEFAULT: react for ANY username mentioned
    if usernames:
        emoji = next_emoji(chat_id)
        try:
            await message.react(emoji)
        except:
            await message.react("❤️")
        return

    # CUSTOM TRIGGERS
    for trig in custom_mentions:
        if trig in text or f"@{trig}" in text:
            emoji = next_emoji(chat_id)
            try:
                await message.react(emoji)
            except:
                await message.react("❤️")
            return
