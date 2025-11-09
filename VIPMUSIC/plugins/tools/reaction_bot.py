# VIPMUSIC/plugins/tools/reaction_bot.py

import random
import logging
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from VIPMUSIC import app

# ✅ Safe config import
try:
    from config import BANNED_USERS, OWNER_ID, START_REACTIONS, REACTION_BOT
except Exception:
    BANNED_USERS = filters.user()
    OWNER_ID = 0
    START_REACTIONS = ["❤️", "💖", "💘", "💞", "💓", "🎧", "✨", "🔥", "💫", "💥", "🎶", "🌸"]
    REACTION_BOT = True

# ✅ Database functions
try:
    from VIPMUSIC.utils.databases import get_reaction_status, set_reaction_status
except Exception as e:
    logging.error(f"[ReactionBot] Database import error: {e}")
    raise

# ✅ Optional sudo users
try:
    from VIPMUSIC.utils.database import get_sudoers
except Exception:
    async def get_sudoers():
        return []


chat_emoji_cycle = {}


def get_next_emoji(chat_id: int) -> str:
    """Pick next emoji (non-repeating per chat)."""
    if chat_id not in chat_emoji_cycle or not chat_emoji_cycle[chat_id]:
        emojis = START_REACTIONS.copy()
        random.shuffle(emojis)
        chat_emoji_cycle[chat_id] = emojis
    return chat_emoji_cycle[chat_id].pop()


async def is_admin_or_sudo(chat_id: int, user_id: int) -> bool:
    """Check if user is admin, owner, or sudo."""
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


# ✅ Reaction control menu
@app.on_message(filters.command(["reaction", "reactionmenu"], prefixes=["/", "!", "."]) & filters.group & ~BANNED_USERS)
async def reaction_menu(client, message: Message):
    chat_id = message.chat.id
    user = message.from_user

    logging.info(f"[ReactionBot] /reaction command by {user.id if user else 'Unknown'} in {chat_id}")

    if not user:
        return await message.reply_text("Unknown user.")

    if not await is_admin_or_sudo(chat_id, user.id):
        return await message.reply_text("Admins or sudo users only!")

    status = get_reaction_status(chat_id)
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Enable", callback_data=f"reaction_enable:{chat_id}"),
                InlineKeyboardButton("❌ Disable", callback_data=f"reaction_disable:{chat_id}"),
            ]
        ]
    )

    text = f"🎭 **Reaction Bot Control**\n\nCurrent status: **{'ON ✅' if status else 'OFF ❌'}**"
    await message.reply_text(text, reply_markup=keyboard)


# ✅ Enable reactions
@app.on_message(filters.command(["reactionon", "reacton"], prefixes=["/", "!", "."]) & filters.group & ~BANNED_USERS)
async def reaction_on(client, message: Message):
    chat_id = message.chat.id
    user = message.from_user

    logging.info(f"[ReactionBot] /reactionon by {user.id if user else 'Unknown'} in {chat_id}")

    if not user:
        return

    if not await is_admin_or_sudo(chat_id, user.id):
        return await message.reply_text("Admins or sudo users only!")

    set_reaction_status(chat_id, True)
    await message.reply_text("✅ **Reactions enabled** in this chat.")


# ✅ Disable reactions
@app.on_message(filters.command(["reactionoff", "reactoff"], prefixes=["/", "!", "."]) & filters.group & ~BANNED_USERS)
async def reaction_off(client, message: Message):
    chat_id = message.chat.id
    user = message.from_user

    logging.info(f"[ReactionBot] /reactionoff by {user.id if user else 'Unknown'} in {chat_id}")

    if not user:
        return

    if not await is_admin_or_sudo(chat_id, user.id):
        return await message.reply_text("Admins or sudo users only!")

    set_reaction_status(chat_id, False)
    await message.reply_text("❌ **Reactions disabled** in this chat.")


# ✅ Callback buttons
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


# ✅ Auto Reaction
@app.on_message(filters.text & filters.group & ~BANNED_USERS)
async def auto_react(client, message: Message):
    chat_id = message.chat.id

    if not REACTION_BOT:
        return
    if not get_reaction_status(chat_id):
        return

    emoji = get_next_emoji(chat_id)
    try:
        await message.react(emoji)
    except Exception:
        pass


print("[ReactionBot] Fully Loaded ✅")
logging.info("[ReactionBot] Ready ✅")
