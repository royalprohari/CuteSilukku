import asyncio
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from VIPMUSIC import app, REACTION_BOT
from VIPMUSIC.utils.database import get_sudoers
from VIPMUSIC.utils.database.reactiondb import get_reaction_status, set_reaction_status
from VIPMUSIC.misc import SUDOERS
from VIPMUSIC.utils.decorators import AdminRightsCheck
from VIPMUSIC.utils.filters import command

BANNED_USERS = filters.user([])

# ------------------------------
# 🔘 BUTTON LAYOUT
# ------------------------------
def reaction_buttons(chat_id: int):
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Enable", callback_data=f"reactionon_{chat_id}"),
                InlineKeyboardButton("🚫 Disable", callback_data=f"reactionoff_{chat_id}"),
            ]
        ]
    )

# ------------------------------
# ⚙️ /reaction Command
# ------------------------------
@app.on_message(command("reaction") & ~BANNED_USERS)
@AdminRightsCheck
async def reaction_toggle(client, message):
    if message.chat.type not in ["group", "supergroup"]:
        return await message.reply_text("❌ This command can only be used in groups.")

    sudoers = await get_sudoers()
    if message.from_user.id not in sudoers and message.from_user.id not in SUDOERS:
        return await message.reply_text("🚫 Only admins or sudo users can manage reactions.")

    chat_id = message.chat.id
    current_status = await get_reaction_status(chat_id)

    # no args → show status menu
    if len(message.command) == 1:
        status_text = "🟢 Enabled" if current_status else "🔴 Disabled"
        return await message.reply_text(
            f"**Reaction Bot is currently {status_text} in this chat.**\n\nUse buttons below to toggle:",
            reply_markup=reaction_buttons(chat_id),
        )

    arg = message.command[1].lower()
    if arg == "on":
        await set_reaction_status(chat_id, True)
        return await message.reply_text("✅ Reaction Bot has been **enabled** for this chat.")
    elif arg == "off":
        await set_reaction_status(chat_id, False)
        return await message.reply_text("🚫 Reaction Bot has been **disabled** for this chat.")
    else:
        return await message.reply_text("Usage:\n`/reaction on` or `/reaction off`")

# ------------------------------
# 🔘 CALLBACK BUTTONS
# ------------------------------
@app.on_callback_query(filters.regex(r"^reactionon_(\d+)$"))
async def cb_enable_reaction(client, query):
    chat_id = int(query.data.split("_")[1])
    await set_reaction_status(chat_id, True)
    await query.message.edit_text(
        "✅ Reaction Bot **enabled** for this chat.",
        reply_markup=reaction_buttons(chat_id),
    )

@app.on_callback_query(filters.regex(r"^reactionoff_(\d+)$"))
async def cb_disable_reaction(client, query):
    chat_id = int(query.data.split("_")[1])
    await set_reaction_status(chat_id, False)
    await query.message.edit_text(
        "🚫 Reaction Bot **disabled** for this chat.",
        reply_markup=reaction_buttons(chat_id),
    )

# ------------------------------
# 💫 AUTO REACTOR
# ------------------------------
@app.on_message(filters.all & ~BANNED_USERS)
async def auto_reactor(client, message):
    if not REACTION_BOT:
        return  # globally disabled in config

    if message.chat.type not in ["group", "supergroup", "private"]:
        return

    chat_id = message.chat.id
    status = await get_reaction_status(chat_id)
    if not status:
        return

    if message.from_user and message.from_user.is_self:
        return

    # Import emoji cycler from your reaction.py
    try:
        from VIPMUSIC.plugins.tools.reaction import next_emoji
        emoji = next_emoji(chat_id)
        await message.react(emoji)
        print(f"[ReactionBot] Reacted in {chat_id} with {emoji}")
    except Exception as e:
        print(f"[ReactionBot] Failed to react in {chat_id}: {e}")
