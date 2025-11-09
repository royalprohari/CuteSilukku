import asyncio
import random
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.enums import ChatMemberStatus

from VIPMUSIC import app
from config import OWNER_ID, BANNED_USERS, REACTION_BOT, START_REACTIONS
from VIPMUSIC.utils.database import get_sudoers
from VIPMUSIC.utils.databases import reactiondb


# ---------------- VALID REACTIONS ----------------
VALID_REACTIONS = {
    "❤️", "💖", "💘", "💞", "💓", "✨", "🔥", "💫",
    "💥", "🌸", "😍", "🥰", "💎", "🌙", "🌹", "😂",
    "😎", "🤩", "😘", "😉", "🤭", "💐", "😻", "🥳"
}

SAFE_REACTIONS = [e for e in START_REACTIONS if e in VALID_REACTIONS]
if not SAFE_REACTIONS:
    SAFE_REACTIONS = list(VALID_REACTIONS)

chat_used_reactions = {}


def next_emoji(chat_id: int) -> str:
    """Return a random, non-repeating emoji per chat."""
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


# ---------------- ADMIN CHECK ----------------
async def is_admin_or_sudo(client, message: Message):
    user_id = getattr(message.from_user, "id", None)
    chat_id = message.chat.id

    sudoers = await get_sudoers()
    if user_id == OWNER_ID or user_id in sudoers:
        return True

    try:
        member = await client.get_chat_member(chat_id, user_id)
        if member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR):
            return True
    except Exception:
        pass

    return False


# ---------------- /reactionon ----------------
@app.on_message(filters.command("reactionon") & filters.group & ~BANNED_USERS)
async def enable_reaction_cmd(client, message: Message):
    if not await is_admin_or_sudo(client, message):
        return await message.reply_text("⚠️ Only admins, sudo users, or owner can use this command.")

    await reactiondb.reaction_on(message.chat.id)
    await message.reply_text("✅ **Reactions Enabled** — Bot will now react to all messages.")


# ---------------- /reactionoff ----------------
@app.on_message(filters.command("reactionoff") & filters.group & ~BANNED_USERS)
async def disable_reaction_cmd(client, message: Message):
    if not await is_admin_or_sudo(client, message):
        return await message.reply_text("⚠️ Only admins, sudo users, or owner can use this command.")

    await reactiondb.reaction_off(message.chat.id)
    await message.reply_text("🚫 **Reactions Disabled** — Bot will stop reacting to messages.")


# ---------------- /reaction ----------------
@app.on_message(filters.command("reaction") & filters.group & ~BANNED_USERS)
async def reaction_toggle_menu(client, message: Message):
    if not await is_admin_or_sudo(client, message):
        return await message.reply_text("⚠️ Only admins, sudo users, or owner can use this command.")

    buttons = [
        [
            InlineKeyboardButton("✅ Enable", callback_data=f"reaction_enable_{message.chat.id}"),
            InlineKeyboardButton("🚫 Disable", callback_data=f"reaction_disable_{message.chat.id}")
        ]
    ]
    await message.reply_text(
        "🎭 **Reaction System Control**\n\nUse buttons below to enable or disable reactions.",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# ---------------- CALLBACK HANDLERS ----------------
@app.on_callback_query(filters.regex("^reaction_(enable|disable)_(.*)$"))
async def reaction_callback(client, callback_query):
    user = callback_query.from_user
    data = callback_query.data.split("_")
    action, chat_id = data[1], int(data[2])

    try:
        member = await client.get_chat_member(chat_id, user.id)
        sudoers = await get_sudoers()
        if not (user.id == OWNER_ID or user.id in sudoers or member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR)):
            return await callback_query.answer("You’re not allowed to control reactions!", show_alert=True)
    except Exception:
        pass

    if action == "enable":
        await reactiondb.reaction_on(chat_id)
        await callback_query.edit_message_text("✅ **Reactions Enabled** — Bot will now react to all messages.")
    else:
        await reactiondb.reaction_off(chat_id)
        await callback_query.edit_message_text("🚫 **Reactions Disabled** — Bot will stop reacting to messages.")


# ---------------- AUTO REACTION ON MESSAGES ----------------
@app.on_message(filters.group & ~BANNED_USERS)
async def auto_react_messages(client, message: Message):
    if not REACTION_BOT:
        return  # disabled globally in config.py

    if not message.text and not message.caption:
        return  # skip non-text

    if message.text and message.text.startswith("/"):
        return  # skip commands

    chat_id = message.chat.id
    if not await reactiondb.is_reaction_on(chat_id):
        return  # reaction disabled for this chat

    try:
        emoji = next_emoji(chat_id)
        await message.react(emoji)
    except Exception:
        try:
            await message.react("❤️")
        except Exception:
            pass
