import asyncio
import random
from typing import Dict
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatMemberStatus, ChatType
from VIPMUSIC import app
from config import BANNED_USERS, START_REACTIONS, OWNER_ID
from VIPMUSIC.misc import SUDOERS
from VIPMUSIC.core.mongo import mongodb

# ---------------- DATABASE ----------------
REACTION_STATUS_COLLECTION = mongodb["reaction_status"]
REACTION_CACHE: Dict[int, bool] = {}

# ---------------- VALID REACTION EMOJIS ----------------
VALID_REACTIONS = {
    "❤️", "💖", "💘", "💞", "💓", "✨", "🔥", "💫",
    "💥", "🌸", "😍", "🥰", "💎", "🌙", "🌹", "😂",
    "😎", "🤩", "😘", "😉", "🤭", "💐", "😻", "🥳"
}

SAFE_REACTIONS = [e for e in START_REACTIONS if e in VALID_REACTIONS]
if not SAFE_REACTIONS:
    SAFE_REACTIONS = list(VALID_REACTIONS)


# ---------------- ADMIN CHECK ----------------
async def is_admin_or_sudo(client, message: Message) -> bool:
    user_id = getattr(message.from_user, "id", None)
    chat_id = message.chat.id
    chat_type = message.chat.type

    # Owner or Sudo
    if user_id and (user_id == OWNER_ID or user_id in SUDOERS):
        return True

    # Linked channel owner
    sender_chat_id = getattr(message.sender_chat, "id", None)
    if sender_chat_id:
        try:
            chat = await client.get_chat(chat_id)
            if getattr(chat, "linked_chat_id", None) == sender_chat_id:
                return True
        except Exception:
            pass

    if chat_type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return False

    if not user_id:
        return False

    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR)
    except Exception:
        return False


# ---------------- REACTION STATUS MANAGEMENT ----------------
async def get_reaction_status(chat_id: int) -> bool:
    """Get reaction status for a chat (cached + database)."""
    if chat_id in REACTION_CACHE:
        return REACTION_CACHE[chat_id]

    try:
        doc = await REACTION_STATUS_COLLECTION.find_one({"chat_id": chat_id})
        status = doc.get("status", True) if doc else True
        REACTION_CACHE[chat_id] = status
        return status
    except Exception as e:
        print(f"[Reaction Bot] Error fetching reaction status for {chat_id}: {e}")
        return True


async def set_reaction_status(chat_id: int, status: bool):
    """Set reaction status for a chat in database."""
    REACTION_CACHE[chat_id] = status
    try:
        await REACTION_STATUS_COLLECTION.update_one(
            {"chat_id": chat_id},
            {"$set": {"status": status}},
            upsert=True
        )
    except Exception as e:
        print(f"[Reaction Bot] Error setting reaction status for {chat_id}: {e}")


# ---------------- /reactionon ----------------
@app.on_message(filters.command("reactionon") & ~BANNED_USERS)
async def reaction_on_command(client, message: Message):
    if not await is_admin_or_sudo(client, message):
        return await message.reply_text("⚠️ Only admins or sudo users can enable reactions.")

    chat_id = message.chat.id
    await set_reaction_status(chat_id, True)
    await message.reply_text("✅ **Reaction mode enabled!**\n\nI will now respond to messages with emoji replies.")


# ---------------- /reactionoff ----------------
@app.on_message(filters.command("reactionoff") & ~BANNED_USERS)
async def reaction_off_command(client, message: Message):
    if not await is_admin_or_sudo(client, message):
        return await message.reply_text("⚠️ Only admins or sudo users can disable reactions.")

    chat_id = message.chat.id
    await set_reaction_status(chat_id, False)
    await message.reply_text("❌ **Reaction mode disabled!**\n\nI will stop responding to messages with emoji replies.")


# ---------------- /reaction ----------------
@app.on_message(filters.command("reaction") & ~BANNED_USERS)
async def reaction_command(client, message: Message):
    if not await is_admin_or_sudo(client, message):
        return await message.reply_text("⚠️ Only admins or sudo users can manage reactions.")

    chat_id = message.chat.id
    current_status = await get_reaction_status(chat_id)

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Enable", callback_data=f"reaction_enable_{chat_id}"),
                InlineKeyboardButton("❌ Disable", callback_data=f"reaction_disable_{chat_id}"),
            ]
        ]
    )

    status_text = "enabled" if current_status else "disabled"
    await message.reply_text(
        f"**🤖 Reaction Settings**\n\n"
        f"**Current Status:** `{status_text}`\n\n"
        f"Use the buttons below to enable or disable reactions:",
        reply_markup=keyboard
    )


# ---------------- CALLBACK QUERY HANDLER ----------------
@app.on_callback_query(filters.regex(r"^reaction_(enable|disable)_(?:-?\d+)$"))
async def reaction_callback_handler(client, callback_query):
    chat_id = int(callback_query.matches[0].group(2))
    action = callback_query.matches[0].group(1)

    # Permission check
    user_id = callback_query.from_user.id
    try:
        member = await client.get_chat_member(chat_id, user_id)
        is_admin = member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR)
        is_sudo = user_id == OWNER_ID or user_id in SUDOERS

        if not (is_admin or is_sudo):
            return await callback_query.answer("❌ You need to be an admin to use this!", show_alert=True)
    except Exception:
        return await callback_query.answer("❌ Error verifying permissions!", show_alert=True)

    if action == "enable":
        await set_reaction_status(chat_id, True)
        await callback_query.message.edit_text(
            "✅ **Reaction mode enabled!**\n\nI will now respond to messages with emoji replies."
        )
    else:
        await set_reaction_status(chat_id, False)
        await callback_query.message.edit_text(
            "❌ **Reaction mode disabled!**\n\nI will stop responding to messages with emoji replies."
        )

    await callback_query.answer()


# ---------------- MESSAGE HANDLER (Random Emoji) ----------------
def is_command(text: str) -> bool:
    """Check if message is a command"""
    return text and text.startswith("/")


@app.on_message((filters.text | filters.caption) & ~BANNED_USERS)
async def reply_with_emoji(client, message: Message):
    try:
        # Ignore commands and replies
        if message.text and is_command(message.text):
            return
        if message.reply_to_message:
            return

        chat_id = message.chat.id

        # Check if reactions are enabled
        reaction_status = await get_reaction_status(chat_id)
        if not reaction_status:
            return

        # Only react in groups
        if message.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
            return

        # Random 20% chance
        if random.random() < 0.2:
            emoji = random.choice(SAFE_REACTIONS)
            try:
                await message.reply_text(emoji)
                print(f"[Reaction Bot] Chat {chat_id} → Replied with {emoji}")
            except Exception as e:
                print(f"[Reaction Bot] Error replying with emoji: {e}")

    except Exception as e:
        print(f"[reply_with_emoji] error: {e}")


# ---------------- /react (manual reaction) ----------------
@app.on_message(filters.command("react") & ~BANNED_USERS)
async def add_emoji_command(client, message: Message):
    """Add random emoji to a replied message."""
    if not message.reply_to_message:
        return await message.reply_text("❌ Please reply to a message to add an emoji!")

    emoji = random.choice(SAFE_REACTIONS)
    original_text = message.reply_to_message.text or message.reply_to_message.caption or ""
    new_text = f"{original_text} {emoji}"

    try:
        await message.reply_to_message.reply_text(new_text)
        await message.delete()
    except Exception as e:
        await message.reply_text(f"❌ Error: {e}")


# ---------------- LOAD REACTION STATUS ON STARTUP ----------------
async def load_reaction_status():
    """Load all chat reaction statuses on startup."""
    try:
        docs = await REACTION_STATUS_COLLECTION.find().to_list(None)
        for doc in docs:
            REACTION_CACHE[doc["chat_id"]] = doc.get("status", True)
        print(f"[Reaction Bot] Loaded reaction status for {len(docs)} chats.")
    except Exception as e:
        print(f"[Reaction Bot] Error loading reaction status: {e}")


# Schedule DB load safely using app.loop
app.loop.create_task(load_reaction_status())

print("[Reaction Bot] ✅ Reaction bot module loaded successfully!")
