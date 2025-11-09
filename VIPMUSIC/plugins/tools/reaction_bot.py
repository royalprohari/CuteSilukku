# VIPMUSIC/plugins/tools/reaction_bot.py

import random
import logging
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from VIPMUSIC import app

# --- Safe config import ---
try:
    from config import BANNED_USERS, OWNER_ID, START_REACTIONS, REACTION_BOT
except Exception:
    BANNED_USERS = filters.user()  # Empty filter fallback
    OWNER_ID = 0
    START_REACTIONS = ["❤️", "💖", "💘", "💞", "💓", "🎧", "✨", "🔥", "💫", "💥", "🎶", "🌸"]
    REACTION_BOT = True

# --- Safe DB imports ---
try:
    from VIPMUSIC.utils.databases import get_reaction_status, set_reaction_status, load_reaction_data
except ImportError:
    logging.error("⚠️ Reaction database import failed.")
    raise

# --- Optional sudo support ---
try:
    from VIPMUSIC.utils.database import get_sudoers
except ImportError:
    async def get_sudoers():
        return []


chat_emoji_cycle = {}
logging.info("[ReactionBot] Loading...")


def get_next_emoji(chat_id: int) -> str:
    """Get next emoji in rotation for chat."""
    global chat_emoji_cycle
    if chat_id not in chat_emoji_cycle or not chat_emoji_cycle[chat_id]:
        emojis = START_REACTIONS.copy()
        random.shuffle(emojis)
        chat_emoji_cycle[chat_id] = emojis
    return chat_emoji_cycle[chat_id].pop()


# --- Permission helper ---
async def is_admin_or_sudo(chat_id: int, user_id: int) -> bool:
    try:
        member = await app.get_chat_member(chat_id, user_id)
        if member.status in ("administrator", "creator"):
            return True
    except Exception:
        pass
    if user_id == OWNER_ID:
        return True
    if user_id in await get_sudoers():
        return True
    return False


# ✅ Command menu: /reaction
@app.on_message(filters.command(["reaction", "reactionmenu"]) & filters.group & ~BANNED_USERS)
async def reaction_menu(client, message: Message):
    chat_id = message.chat.id
    user = message.from_user
    if not user:
        return await message.reply_text("Unknown user.")

    if not await is_admin_or_sudo(chat_id, user.id):
        return await message.reply_text("Admins or sudo users only!")

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Enable", callback_data=f"reaction_enable:{chat_id}"),
                InlineKeyboardButton("❌ Disable", callback_data=f"reaction_disable:{chat_id}"),
            ]
        ]
    )

    status = get_reaction_status(chat_id)
    text = f"🎭 **Reaction Bot Control**\n\nCurrent status: **{'ON ✅' if status else 'OFF ❌'}**"
    await message.reply_text(text, reply_markup=keyboard)


# ✅ Enable command: /reactionon
@app.on_message(filters.command("reactionon") & filters.group & ~BANNED_USERS)
async def reaction_on(client, message: Message):
    chat_id = message.chat.id
    user = message.from_user
    if not user:
        return

    if not await is_admin_or_sudo(chat_id, user.id):
        return await message.reply_text("Admins or sudo users only!")

    set_reaction_status(chat_id, True)
    await message.reply_text("✅ **Reactions have been enabled** in this chat.")


# ✅ Disable command: /reactionoff
@app.on_message(filters.command("reactionoff") & filters.group & ~BANNED_USERS)
async def reaction_off(client, message: Message):
    chat_id = message.chat.id
    user = message.from_user
    if not user:
        return

    if not await is_admin_or_sudo(chat_id, user.id):
        return await message.reply_text("Admins or sudo users only!")

    set_reaction_status(chat_id, False)
    await message.reply_text("❌ **Reactions have been disabled** in this chat.")


# ✅ Inline button handler
@app.on_callback_query(filters.regex("^reaction_(enable|disable):"))
async def reaction_button(client, query):
    user = query.from_user
    chat_id = int(query.data.split(":")[1])
    action = query.data.split(":")[0].replace("reaction_", "")

    if not await is_admin_or_sudo(chat_id, user.id):
        return await query.answer("Admins only!", show_alert=True)

    if action == "enable":
        set_reaction_status(chat_id, True)
        await query.message.edit_text("✅ Reactions have been **enabled** in this chat.")
    else:
        set_reaction_status(chat_id, False)
        await query.message.edit_text("❌ Reactions have been **disabled** in this chat.")


# ✅ Auto React messages
@app.on_message(filters.text & filters.group & ~BANNED_USERS)
async def auto_react(client, message: Message):
    if not REACTION_BOT:
        return
    chat_id = message.chat.id
    if not get_reaction_status(chat_id):
        return
    emoji = get_next_emoji(chat_id)
    try:
        await message.react(emoji)
    except Exception:
        pass


logging.info("[ReactionBot] Loaded successfully ✅")
print("[ReactionBot] Ready ✅")
