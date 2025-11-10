# VIPMUSIC/plugins/tools/reaction_bot.py
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from VIPMUSIC import app
from VIPMUSIC.misc import SUDOERS, OWNER_ID
from VIPMUSIC.utils.databases.reactiondb import reaction_on, reaction_off, is_reaction_on
from config import START_REACTIONS

print("[ReactionBot] Plugin loaded!")

# Helper: check if user is authorized to run commands
async def is_authorized(message: Message) -> bool:
    user_id = message.from_user.id
    chat_id = message.chat.id
    member = await app.get_chat_member(chat_id, user_id)
    if user_id == OWNER_ID or user_id in SUDOERS or member.status in ["administrator", "creator"]:
        return True
    return False

# ------------------ COMMANDS ------------------

@app.on_message(filters.command("reactionon", prefixes="/") & filters.group)
async def reaction_on_cmd(client, message: Message):
    if not await is_authorized(message):
        return await message.reply_text("❌ You are not authorized to use this command!")
    
    await reaction_on(message.chat.id)
    await message.reply_text("✅ Reactions have been **enabled** for this chat!")

@app.on_message(filters.command("reactionoff", prefixes="/") & filters.group)
async def reaction_off_cmd(client, message: Message):
    if not await is_authorized(message):
        return await message.reply_text("❌ You are not authorized to use this command!")
    
    await reaction_off(message.chat.id)
    await message.reply_text("❌ Reactions have been **disabled** for this chat!")

@app.on_message(filters.command("reaction", prefixes="/") & filters.group)
async def reaction_main_cmd(client, message: Message):
    if not await is_authorized(message):
        return await message.reply_text("❌ You are not authorized to use this command!")
    
    chat_id = message.chat.id
    status = await is_reaction_on(chat_id)
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Enable" if not status else "⚪ Already ON", callback_data="reaction_enable"),
            InlineKeyboardButton("❌ Disable" if status else "⚪ Already OFF", callback_data="reaction_disable"),
        ]
    ]
    await message.reply_text(
        f"💫 Reactions are currently: **{'Enabled' if status else 'Disabled'}**",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ------------------ CALLBACK QUERY HANDLERS ------------------

@app.on_callback_query(filters.regex("^reaction_enable$"))
async def reaction_enable_cb(client, callback: CallbackQuery):
    if not await is_authorized(callback.message):
        return await callback.answer("❌ You are not authorized!", show_alert=True)
    
    await reaction_on(callback.message.chat.id)
    await callback.message.edit_text("✅ Reactions have been **enabled** for this chat!", reply_markup=None)
    await callback.answer()

@app.on_callback_query(filters.regex("^reaction_disable$"))
async def reaction_disable_cb(client, callback: CallbackQuery):
    if not await is_authorized(callback.message):
        return await callback.answer("❌ You are not authorized!", show_alert=True)
    
    await reaction_off(callback.message.chat.id)
    await callback.message.edit_text("❌ Reactions have been **disabled** for this chat!", reply_markup=None)
    await callback.answer()

# ------------------ AUTOMATIC REACTIONS ------------------

@app.on_message(filters.group)  # Removed ~filters.edited
async def auto_react(client, message: Message):
    chat_id = message.chat.id
    if not await is_reaction_on(chat_id):
        return
    
    import random
    emoji = random.choice(START_REACTIONS)
    try:
        await message.reply_text(emoji)
    except:
        pass
