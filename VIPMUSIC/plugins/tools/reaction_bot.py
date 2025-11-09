"""
Final reaction_bot.py for VIPMUSIC

Requirements satisfied:
1. /reactionon - react every messages (enable)
2. /reactionoff - Off reaction (disable)
3. /reaction - shows enable/disable inline buttons
4. Works in groups & supergroups (filters.group - Pyrogram v1.x)
5. Commands usable by Owner, Sudo users and Group Admins
6. Per-chat state persisted by VIPMUSIC/utils/databases/reactiondb.py
"""

import random
import traceback
from typing import Set, Dict, Optional

from pyrogram import filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from pyrogram.enums import ChatMemberStatus

from VIPMUSIC import app, LOGGER
import config
from VIPMUSIC.utils.database import get_sudoers
from VIPMUSIC.utils.databases import reactiondb  # expects: reaction_on, reaction_off, is_reaction_on

print("[ReactionBot] plugin import")

# Use START_REACTIONS from config if present, otherwise fallback
try:
    START_REACTIONS = list(config.START_REACTIONS)
except Exception:
    START_REACTIONS = [
        "❤️", "💖", "💘", "💞", "💓", "🎧", "✨", "🔥", "💫",
        "💥", "🎶", "🌸", "💎", "😎", "💗", "🌹", "💕",
    ]

# sanitize dedupe
SAFE_REACTIONS = list(dict.fromkeys(START_REACTIONS))
if not SAFE_REACTIONS:
    SAFE_REACTIONS = ["❤️"]

# per-chat non-repeating rotation cache
_chat_used: Dict[int, Set[str]] = {}


def next_emoji(chat_id: int) -> str:
    used = _chat_used.get(chat_id, set())
    if len(used) >= len(SAFE_REACTIONS):
        used.clear()
    remaining = [e for e in SAFE_REACTIONS if e not in used]
    emoji = random.choice(remaining)
    used.add(emoji)
    _chat_used[chat_id] = used
    return emoji


async def _get_sudoers_list():
    """Return list of sudoers (ints) merging config.SUDOERS and DB sudoers."""
    sudo_list = set()
    # config.SUDOERS may be list of strings; normalize
    try:
        cfg = getattr(config, "SUDOERS", None)
        if cfg:
            # if stored as strings in env split earlier
            if isinstance(cfg, (list, tuple)):
                for v in cfg:
                    try:
                        sudo_list.add(int(v))
                    except Exception:
                        pass
            elif isinstance(cfg, str):
                for v in cfg.split():
                    try:
                        sudo_list.add(int(v))
                    except Exception:
                        pass
    except Exception:
        pass

    # add OWNER_ID from config if present
    try:
        if getattr(config, "OWNER_ID", None):
            sudo_list.add(int(config.OWNER_ID))
    except Exception:
        pass

    # get DB sudoers if available
    try:
        db_sudos = await get_sudoers()
        if db_sudos:
            for u in db_sudos:
                try:
                    sudo_list.add(int(u))
                except Exception:
                    pass
    except Exception:
        # ignore DB errors
        pass

    return sudo_list


async def is_admin_or_sudo(client, user_id: Optional[int], chat_id: int) -> bool:
    """Return True if user is owner, in sudoers list, or an admin in chat."""
    if not user_id:
        return False

    # owner check
    try:
        if getattr(config, "OWNER_ID", None) and int(config.OWNER_ID) == int(user_id):
            return True
    except Exception:
        pass

    # sudoers list check
    try:
        sudoers = await _get_sudoers_list()
        if int(user_id) in sudoers:
            return True
    except Exception:
        pass

    # chat admin check
    try:
        member = await client.get_chat_member(chat_id, user_id)
        if member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR):
            return True
    except Exception:
        # Could be not in chat or RPC error
        LOGGER.debug(f"[ReactionBot] get_chat_member failed for {user_id} in {chat_id}")
        return False

    return False


# ---------------- Test handler (quick verify) ----------------
@app.on_message(filters.command("reactiontest") & filters.group)
async def reaction_test(_, message: Message):
    print("[ReactionBot] /reactiontest triggered")
    await message.reply_text("✅ Reaction test command works!")


# ---------------- /reactionon ----------------
@app.on_message(filters.command(["reactionon", "reactionenable"], prefixes=["/", "!", "."]) & filters.group)
async def cmd_reaction_on(client, message: Message):
    caller_id = getattr(message.from_user, "id", None)
    chat_id = message.chat.id
    print(f"[ReactionBot] /reactionon by {caller_id} in {chat_id}")
    try:
        allowed = await is_admin_or_sudo(client, caller_id, chat_id)
        if not allowed:
            await message.reply_text("❌ Only Owner, Sudo users or Group Admins can enable reactions.")
            LOGGER.info(f"[ReactionBot] /reactionon denied for {caller_id} in {chat_id}")
            return
        await reactiondb.reaction_on(chat_id)
        await message.reply_text("✅ Reactions enabled for this chat.")
        LOGGER.info(f"[ReactionBot] Reactions enabled in {chat_id} by {caller_id}")
    except Exception as e:
        LOGGER.error(f"[ReactionBot] Error in /reactionon: {e}\n{traceback.format_exc()}")
        try:
            await message.reply_text(f"❌ Error enabling reactions:\n`{e}`")
        except Exception:
            pass


# ---------------- /reactionoff ----------------
@app.on_message(filters.command(["reactionoff", "reactiondisable"], prefixes=["/", "!", "."]) & filters.group)
async def cmd_reaction_off(client, message: Message):
    caller_id = getattr(message.from_user, "id", None)
    chat_id = message.chat.id
    print(f"[ReactionBot] /reactionoff by {caller_id} in {chat_id}")
    try:
        allowed = await is_admin_or_sudo(client, caller_id, chat_id)
        if not allowed:
            await message.reply_text("❌ Only Owner, Sudo users or Group Admins can disable reactions.")
            LOGGER.info(f"[ReactionBot] /reactionoff denied for {caller_id} in {chat_id}")
            return
        await reactiondb.reaction_off(chat_id)
        await message.reply_text("🚫 Reactions disabled for this chat.")
        LOGGER.info(f"[ReactionBot] Reactions disabled in {chat_id} by {caller_id}")
    except Exception as e:
        LOGGER.error(f"[ReactionBot] Error in /reactionoff: {e}\n{traceback.format_exc()}")
        try:
            await message.reply_text(f"❌ Error disabling reactions:\n`{e}`")
        except Exception:
            pass


# ---------------- /reaction (status + buttons) ----------------
@app.on_message(filters.command(["reaction", "reactionstatus"], prefixes=["/", "!", "."]) & filters.group)
async def cmd_reaction_status(client, message: Message):
    caller_id = getattr(message.from_user, "id", None)
    chat_id = message.chat.id
    print(f"[ReactionBot] /reaction invoked by {caller_id} in {chat_id}")
    try:
        is_admin = await is_admin_or_sudo(client, caller_id, chat_id)
        status = await reactiondb.is_reaction_on(chat_id)

        status_text = "Enabled ✅" if status else "Disabled ⛔"
        text = f"🎭 Reaction Manager\n\nChat: `{chat_id}`\nStatus: **{status_text}**\n\n(Only Owner, Sudo or Group Admins can toggle)"

        if is_admin:
            if status:
                markup = InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🚫 Disable Reactions", callback_data=f"reaction_disable_{chat_id}")]]
                )
            else:
                markup = InlineKeyboardMarkup(
                    [[InlineKeyboardButton("✅ Enable Reactions", callback_data=f"reaction_enable_{chat_id}")]]
                )
        else:
            markup = None

        await message.reply_text(text, reply_markup=markup)
        LOGGER.info(f"[ReactionBot] status shown in {chat_id} (status={status}) by {caller_id}")
    except Exception as e:
        LOGGER.error(f"[ReactionBot] Error in /reaction: {e}\n{traceback.format_exc()}")
        try:
            await message.reply_text(f"❌ Error showing reaction status:\n`{e}`")
        except Exception:
            pass


# ---------------- Callback handler (buttons) ----------------
@app.on_callback_query(filters.regex(r"^reaction_(enable|disable)_(\-?\d+)$"))
async def reaction_button_handler(client, callback: CallbackQuery):
    data = callback.data or ""
    parts = data.split("_")
    try:
        if len(parts) < 3:
            await callback.answer("Invalid data.", show_alert=True)
            return

        action = parts[1]
        target_chat_id = int(parts[2])
        caller = callback.from_user
        caller_id = getattr(caller, "id", None)

        allowed = await is_admin_or_sudo(client, caller_id, target_chat_id)
        if not allowed:
            await callback.answer("❌ Only Owner, Sudo users or Group Admins can use this.", show_alert=True)
            LOGGER.info(f"[ReactionBot] Unauthorized button press by {caller_id} for {target_chat_id}")
            return

        if action == "enable":
            await reactiondb.reaction_on(target_chat_id)
            await callback.answer("✅ Reactions enabled for this chat.")
            try:
                await callback.message.edit_text(
                    f"🎭 Reaction Manager\n\nChat: `{target_chat_id}`\nStatus: **Enabled ✅**\n\n(Only Owner, Sudo or Group Admins can toggle)",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("🚫 Disable Reactions", callback_data=f"reaction_disable_{target_chat_id}")]]
                    ),
                )
            except Exception:
                pass
            LOGGER.info(f"[ReactionBot] Reactions enabled via button in {target_chat_id} by {caller_id}")
        elif action == "disable":
            await reactiondb.reaction_off(target_chat_id)
            await callback.answer("🚫 Reactions disabled for this chat.")
            try:
                await callback.message.edit_text(
                    f"🎭 Reaction Manager\n\nChat: `{target_chat_id}`\nStatus: **Disabled ⛔**\n\n(Only Owner, Sudo or Group Admins can toggle)",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("✅ Enable Reactions", callback_data=f"reaction_enable_{target_chat_id}")]]
                    ),
                )
            except Exception:
                pass
            LOGGER.info(f"[ReactionBot] Reactions disabled via button in {target_chat_id} by {caller_id}")
        else:
            await callback.answer("Unknown action.", show_alert=True)
    except Exception as e:
        LOGGER.error(f"[ReactionBot] Error in button handler: {e}\n{traceback.format_exc()}")
        try:
            await callback.answer(f"Error: {e}", show_alert=True)
        except Exception:
            pass


# ---------------- Auto-react core behaviour ----------------
@app.on_message((filters.text | filters.caption) & filters.group)
async def auto_react_messages(client, message: Message):
    try:
        # skip commands
        text = (message.text or message.caption or "")
        if isinstance(text, str) and text.startswith("/"):
            return

        chat_id = message.chat.id
        try:
            enabled = await reactiondb.is_reaction_on(chat_id)
        except Exception as e:
            LOGGER.error(f"[ReactionBot] DB error is_reaction_on for {chat_id}: {e}")
            enabled = True  # fail-safe

        if not enabled:
            return

        emoji = next_emoji(chat_id)
        try:
            await message.react(emoji)
            LOGGER.info(f"[ReactionBot] Auto-reacted in {chat_id} with {emoji}")
        except Exception as e:
            LOGGER.warning(f"[ReactionBot] Primary react failed in {chat_id}: {e}")
            try:
                await message.react("❤️")
            except Exception:
                pass

    except Exception as e:
        LOGGER.error(f"[ReactionBot] Error in auto_react_messages: {e}\n{traceback.format_exc()}")

print("[ReactionBot] plugin loaded successfully")
