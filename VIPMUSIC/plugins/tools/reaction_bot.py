import asyncio
import random
import traceback
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
    try:
        user_id = getattr(message.from_user, "id", None)
        chat_id = message.chat.id

        sudoers = await get_sudoers()
        if user_id == OWNER_ID or user_id in sudoers:
            return True

        member = await client.get_chat_member(chat_id, user_id)
        if member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR):
            return True
    except Exception as e:
        print(f"[is_admin_or_sudo] Error: {e}")
        traceback.print_exc()

    return False


# ---------------- /reactionon ----------------
@app.on_message(filters.command("reactionon") & filters.group & ~BANNED_USERS)
async def enable_reaction_cmd(client, message: Message):
    try:
        ok = await is_admin_or_sudo(client, message)
        if not ok:
            return await message.reply_text("⚠️ Only admins, sudo users, or owner can use this command.")

        await reactiondb.reaction_on(message.chat.id)
        await message.reply_text("✅ **Reactions Enabled** — Bot will now react to all messages.")
        print(f"[reactionon] Chat {message.chat.id}: reactions enabled.")
    except Exception as e:
        print(f"[reactionon] Error in chat {message.chat.id}: {e}")
        traceback.print_exc()
        await message.reply_text(f"❌ Error enabling reaction:\n`{e}`")


# ---------------- /reactionoff ----------------
@app.on_message(filters.command("reactionoff") & filters.group & ~BANNED_USERS)
async def disable_reaction_cmd(client, message: Message):
    try:
        ok = await is_admin_or_sudo(client, message)
        if not ok:
            return await message.reply_text("⚠️ Only admins, sudo users, or owner can use this command.")

        await reactiondb.reaction_off(message.chat.id)
        await message.reply_text("🚫 **Reactions Disabled** — Bot will stop reacting to messages.")
        print(f"[reactionoff] Chat {message.chat.id}: reactions disabled.")
    except Exception as e:
        print(f"[reactionoff] Error in chat {message.chat.id}: {e}")
        traceback.print_exc()
        await message.reply_text(f"❌ Error disabling reaction:\n`{e}`")


# ---------------- /reaction ----------------
@app.on_message(filters.command("reaction") & filters.group & ~BANNED_USERS)
async def reaction_toggle_menu(client, message: Message):
    try:
        ok = await is_admin_or_sudo(client, message)
        if not ok:
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
        print(f"[reaction command] Menu shown in chat {message.chat.id}")
    except Exception as e:
        print(f"[reaction] Error in chat {message.chat.id}: {e}")
        traceback.print_exc()
        await message.reply_text(f"❌ Error showing reaction menu:\n`{e}`")


# ---------------- CALLBACK HANDLERS ----------------
@app.on_callback_query(filters.regex("^reaction_(enable|disable)_(.*)$"))
async def reaction_callback(client, callback_query):
    try:
        user = callback_query.from_user
        data = callback_query.data.split("_")
        action, chat_id = data[1], int(data[2])

        member = await client.get_chat_member(chat_id, user.id)
        sudoers = await get_sudoers()

        if not (user.id == OWNER_ID or user.id in sudoers or member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR)):
            return await callback_query.answer("You’re not allowed to control reactions!", show_alert=True)

        if action == "enable":
            await reactiondb.reaction_on(chat_id)
            await callback_query.edit_message_text("✅ **Reactions Enabled** — Bot will now react to all messages.")
            print(f"[callback] Chat {chat_id}: reactions enabled by {user.id}")
        else:
            await reactiondb.reaction_off(chat_id)
            await callback_query.edit_message_text("🚫 **Reactions Disabled** — Bot will stop reacting to messages.")
            print(f"[callback] Chat {chat_id}: reactions disabled by {user.id}")
    except Exception as e:
        print(f"[reaction_callback] Error: {e}")
        traceback.print_exc()
        try:
            await callback_query.answer(f"Error: {e}", show_alert=True)
        except:
            pass


# ---------------- AUTO REACTION ON MESSAGES ----------------
@app.on_message(filters.group & ~BANNED_USERS)
async def auto_react_messages(client, message: Message):
    try:
        if not REACTION_BOT:
            return  # disabled globally in config.py

        if not message.text and not message.caption:
            return

        if message.text and message.text.startswith("/"):
            return

        chat_id = message.chat.id
        if not await reactiondb.is_reaction_on(chat_id):
            return

        emoji = next_emoji(chat_id)
        await message.react(emoji)
        print(f"[AutoReaction] Chat {chat_id} reacted with {emoji}")

    except Exception as e:
        print(f"[auto_react_messages] Error in chat {message.chat.id}: {e}")
        traceback.print_exc()
        try:
            await message.react("❤️")
        except Exception:
            pass
