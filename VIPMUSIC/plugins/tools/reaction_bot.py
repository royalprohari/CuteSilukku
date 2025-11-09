"""
VIPMUSIC/plugins/tools/reaction_bot.py

Features:
- /reactionon, /reactionoff: enable/disable per-chat reactions (Owner/Sudo/Admin)
- /reaction: shows inline Enable / Disable buttons
- Callback handlers for the buttons (checks permissions)
- Auto-react to messages (per-chat, non-repeating emoji rotation using START_REACTIONS)
- Logging to console and to file reaction_command_debug.log
- Uses VIPMUSIC.utils.databases.reactiondb for persistence:
    - reactiondb.reaction_on(chat_id)
    - reactiondb.reaction_off(chat_id)
    - reactiondb.is_reaction_on(chat_id)
"""

import asyncio
import random
import logging
import traceback
from typing import Set, Dict

from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from pyrogram.enums import ChatMemberStatus

from VIPMUSIC import app
from config import OWNER_ID, BANNED_USERS, START_REACTIONS
from VIPMUSIC.utils.database import get_sudoers
from VIPMUSIC.utils.databases import reactiondb

# ----------------- Logging Setup -----------------
logger = logging.getLogger("reaction_bot")
handler = logging.FileHandler("reaction_command_debug.log", mode="a", encoding="utf-8")
formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

def log_info(msg: str):
    print(f"[ReactionBot] {msg}")
    logger.info(msg)

def log_error(msg: str):
    print(f"[ReactionBot][ERROR] {msg}")
    logger.exception(msg)

log_info("Loading reaction_bot plugin...")

# ----------------- Valid Reactions -----------------
VALID_REACTIONS = {
    "❤️", "💖", "💘", "💞", "💓", "✨", "🔥", "💫",
    "💥", "🌸", "😍", "🥰", "💎", "🌙", "🌹", "😂",
    "😎", "🤩", "😘", "😉", "🤭", "💐", "😻", "🥳", "🎧", "🎶"
}

# Use START_REACTIONS from config but filter against VALID_REACTIONS
SAFE_REACTIONS = [e for e in START_REACTIONS if e in VALID_REACTIONS]
if not SAFE_REACTIONS:
    SAFE_REACTIONS = list(VALID_REACTIONS)

# ----------------- Per-chat emoji rotation cache -----------------
# Maps chat_id -> set(of used emojis)
chat_used_reactions: Dict[int, Set[str]] = {}

def next_emoji(chat_id: int) -> str:
    """Return a random non-repeating emoji for the chat."""
    if chat_id not in chat_used_reactions:
        chat_used_reactions[chat_id] = set()

    used = chat_used_reactions[chat_id]
    if len(used) >= len(SAFE_REACTIONS):
        # all used -> reset
        used.clear()

    remaining = [e for e in SAFE_REACTIONS if e not in used]
    emoji = random.choice(remaining)
    used.add(emoji)
    chat_used_reactions[chat_id] = used
    return emoji

# ----------------- Admin / Sudo check -----------------
async def is_admin_or_sudo(client, message: Message) -> bool:
    try:
        user = message.from_user
        user_id = getattr(user, "id", None)
        chat_id = message.chat.id

        # owner / sudo check
        try:
            sudoers = await get_sudoers()
        except Exception:
            sudoers = []
        if user_id and (user_id == OWNER_ID or user_id in sudoers):
            log_info(f"is_admin_or_sudo: user {user_id} is owner/sudo")
            return True

        # If message sent by a channel (sender_chat) or no from_user, deny
        if not user_id:
            log_info(f"is_admin_or_sudo: no from_user for message in chat {chat_id}")
            return False

        # chat admin check
        try:
            member = await client.get_chat_member(chat_id, user_id)
            if member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR):
                log_info(f"is_admin_or_sudo: user {user_id} is admin in chat {chat_id}")
                return True
            else:
                log_info(f"is_admin_or_sudo: user {user_id} not admin (status={member.status}) in chat {chat_id}")
        except Exception as e:
            log_error(f"is_admin_or_sudo: get_chat_member failed for user {user_id} in chat {chat_id}: {e}")
            # fall back to False
            return False

    except Exception as e:
        log_error(f"is_admin_or_sudo unknown error: {e}")
        return False

    return False

# ----------------- Command: /reactionon -----------------
@app.on_message(filters.command(["reactionon"], prefixes=["/", "!", "."]) & filters.group & ~BANNED_USERS)
async def cmd_reaction_on(client, message: Message):
    try:
        log_info(f"Command /reactionon received in chat {message.chat.id} from {getattr(message.from_user,'id', None)}")
        # permission check
        ok = await is_admin_or_sudo(client, message)
        if not ok:
            await message.reply_text("⚠️ Only the Owner, sudo users or group admins can enable reactions.")
            log_info(f"/reactionon denied for user {getattr(message.from_user,'id', None)} in chat {message.chat.id}")
            return

        await reactiondb.reaction_on(message.chat.id)
        await message.reply_text("✅ Reactions enabled for this chat.")
        log_info(f"Reactions enabled for chat {message.chat.id}")
    except Exception as e:
        log_error(f"Error in /reactionon handler: {e}\n{traceback.format_exc()}")
        try:
            await message.reply_text(f"❌ Error enabling reactions:\n`{e}`")
        except Exception:
            pass

# ----------------- Command: /reactionoff -----------------
@app.on_message(filters.command(["reactionoff"], prefixes=["/", "!", "."]) & filters.group & ~BANNED_USERS)
async def cmd_reaction_off(client, message: Message):
    try:
        log_info(f"Command /reactionoff received in chat {message.chat.id} from {getattr(message.from_user,'id', None)}")
        ok = await is_admin_or_sudo(client, message)
        if not ok:
            await message.reply_text("⚠️ Only the Owner, sudo users or group admins can disable reactions.")
            log_info(f"/reactionoff denied for user {getattr(message.from_user,'id', None)} in chat {message.chat.id}")
            return

        await reactiondb.reaction_off(message.chat.id)
        await message.reply_text("🚫 Reactions disabled for this chat.")
        log_info(f"Reactions disabled for chat {message.chat.id}")
    except Exception as e:
        log_error(f"Error in /reactionoff handler: {e}\n{traceback.format_exc()}")
        try:
            await message.reply_text(f"❌ Error disabling reactions:\n`{e}`")
        except Exception:
            pass

# ----------------- Command: /reaction (menu) -----------------
@app.on_message(filters.command(["reaction"], prefixes=["/", "!", "."]) & filters.group & ~BANNED_USERS)
async def cmd_reaction_menu(client, message: Message):
    try:
        log_info(f"Command /reaction (menu) received in chat {message.chat.id} from {getattr(message.from_user,'id', None)}")
        ok = await is_admin_or_sudo(client, message)
        if not ok:
            await message.reply_text("⚠️ Only the Owner, sudo users or group admins can use this command.")
            return

        # Build buttons
        buttons = [
            [
                InlineKeyboardButton("✅ Enable", callback_data=f"reaction_toggle:enable:{message.chat.id}"),
                InlineKeyboardButton("🚫 Disable", callback_data=f"reaction_toggle:disable:{message.chat.id}")
            ],
            [InlineKeyboardButton("Close ✖", callback_data=f"reaction_toggle:close:{message.chat.id}")]
        ]
        # Show current status
        status = await reactiondb.is_reaction_on(message.chat.id)
        status_text = "Enabled ✅" if status else "Disabled ⛔"
        text = (
            f"🎭 **Reaction Manager**\n\n"
            f"Chat: `{message.chat.id}`\n"
            f"Status: **{status_text}**\n\n"
            f"Only Owner, sudo users or chat admins can press the buttons."
        )

        await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        log_info(f"Reaction menu shown in chat {message.chat.id} (status={status_text})")
    except Exception as e:
        log_error(f"Error in /reaction menu handler: {e}\n{traceback.format_exc()}")
        try:
            await message.reply_text(f"❌ Error showing reaction menu:\n`{e}`")
        except Exception:
            pass

# ----------------- Callback handler for the inline buttons -----------------
@app.on_callback_query(filters.regex(r"^reaction_toggle:(enable|disable|close):(-?\d+)$"))
async def reaction_toggle_callback(client, callback: CallbackQuery):
    try:
        data = callback.data or ""
        parts = data.split(":")
        if len(parts) != 3:
            await callback.answer("Invalid action.", show_alert=True)
            return

        action = parts[1]
        target_chat_id = int(parts[2])
        caller = callback.from_user
        caller_id = getattr(caller, "id", None)

        # Permission: owner/sudo or admin in that chat (if callback invoked in same chat)
        allowed = False
        try:
            sudoers = await get_sudoers()
        except Exception:
            sudoers = []

        if caller_id and (caller_id == OWNER_ID or caller_id in sudoers):
            allowed = True
        else:
            # if callback invoked in same chat message, check admin
            try:
                msg_chat_id = callback.message.chat.id
            except Exception:
                msg_chat_id = None

            if msg_chat_id == target_chat_id and caller_id:
                try:
                    member = await client.get_chat_member(target_chat_id, caller_id)
                    if member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR):
                        allowed = True
                except Exception:
                    allowed = False

        if not allowed:
            await callback.answer("Only owner, sudo users or group admins can use this.", show_alert=True)
            log_info(f"Unauthorized callback attempt by {caller_id} for chat {target_chat_id}")
            return

        if action == "close":
            try:
                await callback.message.delete()
            except Exception:
                pass
            await callback.answer()
            return

        if action == "enable":
            await reactiondb.reaction_on(target_chat_id)
            await callback.answer("Reactions enabled for this chat.")
            log_info(f"Callback: enabled reactions for chat {target_chat_id} by {caller_id}")
        elif action == "disable":
            await reactiondb.reaction_off(target_chat_id)
            await callback.answer("Reactions disabled for this chat.")
            log_info(f"Callback: disabled reactions for chat {target_chat_id} by {caller_id}")
        else:
            await callback.answer("Unknown action.", show_alert=True)

        # Try to edit message to show new status
        try:
            status = await reactiondb.is_reaction_on(target_chat_id)
            status_text = "Enabled ✅" if status else "Disabled ⛔"
            new_text = (
                f"🎭 **Reaction Manager**\n\n"
                f"Chat: `{target_chat_id}`\n"
                f"Status: **{status_text}**\n\n"
                f"Only Owner, sudo users or chat admins can press the buttons."
            )
            # reuse markup (buttons remain)
            await callback.message.edit_text(new_text, reply_markup=callback.message.reply_markup)
        except Exception:
            # ignoring edit errors
            pass

    except Exception as e:
        log_error(f"Error in reaction_toggle_callback: {e}\n{traceback.format_exc()}")
        try:
            await callback.answer(f"Error: {e}", show_alert=True)
        except Exception:
            pass

# ----------------- Auto react on messages -----------------
@app.on_message((filters.text | filters.caption) & filters.group & ~BANNED_USERS)
async def auto_react_messages(client, message: Message):
    try:
        # Skip bot commands
        if message.text and message.text.startswith("/"):
            return

        chat_id = message.chat.id
        # Check DB for enabled status
        try:
            enabled = await reactiondb.is_reaction_on(chat_id)
        except Exception as e:
            log_error(f"is_reaction_on DB error for chat {chat_id}: {e}")
            enabled = True  # fail-safe: enable reactions when DB check fails

        if not enabled:
            return

        # choose emoji and react
        emoji = next_emoji(chat_id)
        try:
            await message.react(emoji)
            log_info(f"Auto-reacted in chat {chat_id} with {emoji}")
        except Exception as e:
            log_error(f"Failed to react with {emoji} in chat {chat_id}: {e}")
            # fallback to ❤️
            try:
                await message.react("❤️")
            except Exception:
                pass

    except Exception as e:
        log_error(f"Error in auto_react_messages: {e}\n{traceback.format_exc()}")

log_info("reaction_bot plugin loaded successfully.")
