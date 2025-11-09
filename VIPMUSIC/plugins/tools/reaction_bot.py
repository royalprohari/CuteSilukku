from VIPMUSIC import app
from pyrogram import filters
from VIPMUSIC.utils.databases.reactiondb import is_reaction_on, reaction_on, reaction_off
from config import OWNER_ID, SUDOERS

print("[ReactionBot] Plugin loaded!")

# Filter: Only Owner, Sudo, or Group Admin
async def is_auth_user(_, message):
    user_id = message.from_user.id
    # Group admin check
    member = await message.chat.get_member(user_id)
    if user_id == OWNER_ID or user_id in map(int, SUDOERS) or member.status in ("administrator", "creator"):
        return True
    return False

# --- /reactionon command ---
@app.on_message(
    filters.command("reactionon", prefixes="/") &
    filters.chat_type.in_({"group", "supergroup"}) &
    filters.create(is_auth_user)
)
async def reactionon(_, message):
    await reaction_on(message.chat.id)
    await message.reply_text("✅ Reactions are now **ON** for this group!")

# --- /reactionoff command ---
@app.on_message(
    filters.command("reactionoff", prefixes="/") &
    filters.chat_type.in_({"group", "supergroup"}) &
    filters.create(is_auth_user)
)
async def reactionoff(_, message):
    await reaction_off(message.chat.id)
    await message.reply_text("❌ Reactions are now **OFF** for this group!")

# --- /reaction button command ---
@app.on_message(
    filters.command("reaction", prefixes="/") &
    filters.chat_type.in_({"group", "supergroup"}) &
    filters.create(is_auth_user)
)
async def reaction_buttons(_, message):
    from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Enable ✅", callback_data="reaction_enable"),
                InlineKeyboardButton("Disable ❌", callback_data="reaction_disable"),
            ]
        ]
    )
    await message.reply_text(
        "Select reaction mode for this group:", reply_markup=keyboard
    )

# --- Handle button presses ---
@app.on_callback_query(filters.regex(r"reaction_(enable|disable)"))
async def button_reaction(_, cq):
    chat_id = cq.message.chat.id
    if cq.data == "reaction_enable":
        await reaction_on(chat_id)
        await cq.answer("✅ Reactions Enabled")
    else:
        await reaction_off(chat_id)
        await cq.answer("❌ Reactions Disabled")
