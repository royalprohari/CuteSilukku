# VIPMUSIC/plugins/tools/reaction_bot.py
from VIPMUSIC import app
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from VIPMUSIC.misc import SUDOERS, OWNER_ID
from VIPMUSIC.utils.databases.reactiondb import is_reaction_on, reaction_on, reaction_off
from config import START_REACTIONS
import random

print("[ReactionBot] Plugin loaded!")

# --- Reaction emojis from config ---
REACTIONS = START_REACTIONS or ["❤️", "💖", "💘", "💞", "💓", "🎧", "✨", "🔥", "💫", "💥", "🎶", "🌸"]

# --- Helper to check permission ---
async def is_authorized(message: Message):
    user_id = message.from_user.id if message.from_user else None
    if not user_id:
        return False
    # Owner or Sudo
    if user_id in SUDOERS or user_id == OWNER_ID:
        return True
    # Chat admin or creator
    member = await message.chat.get_member(user_id)
    if member.status in ["administrator", "creator"]:
        return True
    return False

# --- Command: /reactionon ---
@app.on_message(filters.command("reactionon", prefixes="/") & filters.group)
async def cmd_reaction_on(_, message: Message):
    if not await is_authorized(message):
        return await message.reply_text("❌ You are not authorized to use this command!")
    await reaction_on(message.chat.id)
    await message.reply_text("✅ Reactions enabled in this chat.")

# --- Command: /reactionoff ---
@app.on_message(filters.command("reactionoff", prefixes="/") & filters.group)
async def cmd_reaction_off(_, message: Message):
    if not await is_authorized(message):
        return await message.reply_text("❌ You are not authorized to use this command!")
    await reaction_off(message.chat.id)
    await message.reply_text("❌ Reactions disabled in this chat.")

# --- Command: /reaction (show enable/disable buttons) ---
@app.on_message(filters.command("reaction", prefixes="/") & filters.group)
async def cmd_reaction_buttons(_, message: Message):
    if not await is_authorized(message):
        return await message.reply_text("❌ You are not authorized to use this command!")
    
    status = await is_reaction_on(message.chat.id)
    keyboard = [
        [
            InlineKeyboardButton("✅ Enable" if not status else "✅ Enabled", callback_data="reaction_enable"),
            InlineKeyboardButton("❌ Disable" if status else "❌ Disabled", callback_data="reaction_disable")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await message.reply_text("🎯 Manage reactions in this chat:", reply_markup=reply_markup)

# --- CallbackQuery for buttons ---
@app.on_callback_query(filters.regex("reaction_(enable|disable)"))
async def reaction_button_callback(_, callback: CallbackQuery):
    if not await is_authorized(callback.message):
        return await callback.answer("❌ You are not authorized!", show_alert=True)
    
    action = callback.data.split("_")[1]
    if action == "enable":
        await reaction_on(callback.message.chat.id)
        await callback.answer("✅ Reactions enabled!", show_alert=True)
    else:
        await reaction_off(callback.message.chat.id)
        await callback.answer("❌ Reactions disabled!", show_alert=True)
    
    # Update buttons
    status = await is_reaction_on(callback.message.chat.id)
    keyboard = [
        [
            InlineKeyboardButton("✅ Enable" if not status else "✅ Enabled", callback_data="reaction_enable"),
            InlineKeyboardButton("❌ Disable" if status else "❌ Disabled", callback_data="reaction_disable")
        ]
    ]
    await callback.message.edit_reply_markup(InlineKeyboardMarkup(keyboard))

# --- Auto reaction on every message ---
@app.on_message(filters.group & ~filters.service)
async def auto_react(_, message: Message):
    if await is_reaction_on(message.chat.id):
        emoji = random.choice(REACTIONS)
        try:
            await message.reply_text(emoji)
        except:
            pass  # ignore failures
