import asyncio
import random
from typing import Set, Dict, Optional, Tuple
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatMemberStatus

from VIPMUSIC import app
from config import BANNED_USERS, REACTION_BOT, OWNER_ID, START_REACTIONS
from VIPMUSIC.utils.database import mongodb, get_sudoers

# -------------------- DATABASE --------------------
COLLECTION = mongodb["reaction_bot_chats"]

# -------------------- CACHE --------------------
reaction_enabled_chats: Set[int] = set()
chat_used_reactions: Dict[int, Set[str]] = {}

# -------------------- EMOJI CONFIG --------------------
VALID_REACTIONS = {
    "❤️", "💖", "💘", "💞", "💓", "💫", "🔥", "💥",
    "🎶", "🌸", "😍", "🥰", "💎", "🌙", "🌹", "😂",
    "😎", "🤩", "😘", "😉", "💐", "😻", "🥳"
}
SAFE_REACTIONS = [e for e in START_REACTIONS if e in VALID_REACTIONS] or list(VALID_REACTIONS)

# -------------------- LOAD SAVED CHAT STATES --------------------
async def load_reaction_chats():
    try:
        docs = await COLLECTION.find().to_list(None)
        for doc in docs:
            chat_id = doc.get("chat_id")
            if chat_id:
                reaction_enabled_chats.add(chat_id)
        print(f"[ReactionBot] Loaded {len(reaction_enabled_chats)} chat statuses from DB.")
    except Exception as e:
        print(f"[ReactionBot] Error loading chat states: {e}")

asyncio.get_event_loop().create_task(load_reaction_chats())

# -------------------- UTILITIES --------------------
def next_emoji(chat_id: int) -> str:
    if chat_id not in chat_used_reactions:
        chat_used_reactions[chat_id] = set()
    used = chat_used_reactions[chat_id]
    if len(used) >= len(SAFE_REACTIONS):
        used.clear()
    remaining = [e for e in SAFE_REACTIONS if e not in used]
    emoji = random.choice(remaining)
    used.add(emoji)
    return emoji

async def is_admin_or_sudo(client, message: Message) -> Tuple[bool, Optional[str]]:
    user_id = getattr(message.from_user, "id", None)
    chat_id = message.chat.id
    chat_type = getattr(message.chat, "type", "").lower()

    if not user_id:
        return False, "no from_user"

    try:
        sudoers = await get_sudoers()
    except Exception as e:
        print(f"[ReactionBot] get_sudoers error: {e}")
        sudoers = set()

    if user_id == OWNER_ID or user_id in sudoers:
        return True, None

    if chat_type not in ("group", "supergroup"):
        return False, f"chat_type={chat_type}"

    try:
        member = await client.get_chat_member(chat_id, user_id)
        if member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR):
            return True, None
        return False, f"user_status={member.status}"
    except Exception as e:
        return False, str(e)

# -------------------- COMMAND HANDLER --------------------
@app.on_message(filters.command("reaction") & ~BANNED_USERS & (filters.group | filters.supergroup))
async def toggle_reaction_command(client, message: Message):
    chat_id = message.chat.id
    args = message.text.split(maxsplit=1)
    print(f"[ReactionBot] /reaction called in chat_id={chat_id} args={args}")

    # Permission check
    ok, debug = await is_admin_or_sudo(client, message)
    if not ok:
        return await message.reply_text(
            f"⚠️ Only Admins, Owners, or Sudoers can use this command.\nDebug: {debug or 'unknown'}",
            quote=True,
        )

    # No argument — show status with buttons
    if len(args) < 2:
        status = "✅ Enabled" if chat_id in reaction_enabled_chats else "❌ Disabled"
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("🔛 Enable", callback_data=f"react_on:{chat_id}"),
                    InlineKeyboardButton("🔴 Disable", callback_data=f"react_off:{chat_id}")
                ]
            ]
        )
        return await message.reply_text(
            f"🤖 Reaction Bot is currently **{status}** in this chat.",
            reply_markup=keyboard
        )

    # Text-based toggle (/reaction on /reaction off)
    action = args[1].strip().lower()
    if action == "on":
        await enable_reaction(chat_id, message)
    elif action == "off":
        await disable_reaction(chat_id, message)
    else:
        await message.reply_text("Usage: `/reaction on` or `/reaction off`", quote=True)


# -------------------- CALLBACK BUTTON HANDLERS --------------------
@app.on_callback_query(filters.regex(r"^react_(on|off):(\-?\d+)$"))
async def reaction_button_handler(client, callback_query):
    action, chat_id_str = callback_query.data.split(":")
    chat_id = int(chat_id_str)
    message = callback_query.message

    ok, debug = await is_admin_or_sudo(client, message)
    if not ok:
        return await callback_query.answer("⚠️ Only admins can toggle reactions!", show_alert=True)

    if action == "on":
        await enable_reaction(chat_id, message, is_callback=True)
        await callback_query.answer("✅ Reaction Bot Enabled")
    elif action == "off":
        await disable_reaction(chat_id, message, is_callback=True)
        await callback_query.answer("💤 Reaction Bot Disabled")


# -------------------- TOGGLE FUNCTIONS --------------------
async def enable_reaction(chat_id: int, message: Message, is_callback=False):
    try:
        await COLLECTION.update_one({"chat_id": chat_id}, {"$set": {"chat_id": chat_id}}, upsert=True)
        reaction_enabled_chats.add(chat_id)
        print(f"[ReactionBot] Enabled reactions in {chat_id}")
        reply = "✅ Reaction Bot **Enabled** for this chat!"
        if not is_callback:
            await message.reply_text(reply)
        else:
            await message.edit_text(reply)
    except Exception as e:
        print(f"[ReactionBot] Enable DB error: {e}")
        await message.reply_text(f"❌ DB Error: {e}")

async def disable_reaction(chat_id: int, message: Message, is_callback=False):
    try:
        await COLLECTION.delete_one({"chat_id": chat_id})
        reaction_enabled_chats.discard(chat_id)
        print(f"[ReactionBot] Disabled reactions in {chat_id}")
        reply = "💤 Reaction Bot **Disabled** for this chat!"
        if not is_callback:
            await message.reply_text(reply)
        else:
            await message.edit_text(reply)
    except Exception as e:
        print(f"[ReactionBot] Disable DB error: {e}")
        await message.reply_text(f"❌ DB Error: {e}")


# -------------------- AUTO REACTION --------------------
@app.on_message(
    (filters.text | filters.sticker | filters.photo | filters.video | filters.document)
    & ~BANNED_USERS
    & (filters.group | filters.supergroup)
)
async def auto_react(client, message: Message):
    if not REACTION_BOT:
        return
    chat_id = message.chat.id
    if chat_id not in reaction_enabled_chats:
        return
    if message.text and message.text.startswith("/"):
        return
    try:
        emoji = next_emoji(chat_id)
        await message.react(emoji)
        print(f"[ReactionBot] Reacted in {chat_id} with {emoji}")
    except Exception as e:
        print(f"[ReactionBot] Error reacting: {e}")
