import random
from pyrogram import filters
from pyrogram.types import Message
from VIPMUSIC import app, SUDOERS
from VIPMUSIC.utils.database import get_reactdb, set_reactdb

# ---------------- EMOJI CONFIG ----------------
VALID_REACTIONS = [
    "❤️", "💖", "💘", "💞", "💓", "💫", "💥", "✨",
    "🌸", "🌹", "💎", "🌙", "🔥", "🥰", "😍",
    "😘", "😉", "🤩", "😂", "😎", "💐", "😻", "🥳"
]

# Track recently used emojis globally
used_emojis = []
MAX_HISTORY = 6  # don’t reuse last 6 emojis globally

def next_emoji() -> str:
    """Return a random emoji that’s not recently used."""
    global used_emojis
    available = [e for e in VALID_REACTIONS if e not in used_emojis]
    if not available:  # reset if all used
        used_emojis.clear()
        available = VALID_REACTIONS.copy()
    emoji = random.choice(available)
    used_emojis.append(emoji)
    if len(used_emojis) > MAX_HISTORY:
        used_emojis.pop(0)
    return emoji


# ---------------- LOAD REACT TRIGGERS ----------------
custom_mentions = set()
try:
    data = get_reactdb()
    if data:
        custom_mentions.update(data)
        print(f"[ReactDB] Loaded {len(custom_mentions)} triggers.")
except Exception as e:
    print(f"[ReactDB] Load failed: {e}")


# ---------------- ADD REACTION ----------------
@app.on_message(filters.command(["addreact"]) & SUDOERS)
async def add_react(_, message: Message):
    if not message.reply_to_message and len(message.command) < 2:
        return await message.reply_text("Reply to someone or give a word to add as a reaction trigger!")

    if message.reply_to_message:
        user = message.reply_to_message.from_user
        if not user:
            return await message.reply_text("User not found.")
        custom_mentions.add(str(user.id))
        await set_reactdb(custom_mentions)
        return await message.reply_text(f"✨ Added **{user.mention}** to the reaction list.")

    trigger = message.text.split(None, 1)[1].strip().lower()
    custom_mentions.add(trigger)
    await set_reactdb(custom_mentions)
    await message.reply_text(f"✨ Added trigger `{trigger}` to the reaction list.")


# ---------------- REMOVE REACTION ----------------
@app.on_message(filters.command(["delreact"]) & SUDOERS)
async def del_react(_, message: Message):
    if message.reply_to_message:
        user = message.reply_to_message.from_user
        if user and str(user.id) in custom_mentions:
            custom_mentions.remove(str(user.id))
            await set_reactdb(custom_mentions)
            return await message.reply_text(f"❌ Removed **{user.mention}** from the reaction list.")

    if len(message.command) < 2:
        return await message.reply_text("Give a trigger or reply to someone to remove reaction trigger!")

    trigger = message.text.split(None, 1)[1].strip().lower()
    if trigger in custom_mentions:
        custom_mentions.remove(trigger)
        await set_reactdb(custom_mentions)
        await message.reply_text(f"❌ Removed trigger `{trigger}` from the reaction list.")
    else:
        await message.reply_text(f"Trigger `{trigger}` not found.")


# ---------------- CLEAR REACTIONS ----------------
@app.on_message(filters.command(["clearreact"]) & SUDOERS)
async def clear_react(_, message: Message):
    custom_mentions.clear()
    await set_reactdb(custom_mentions)
    await message.reply_text("🧹 Cleared all reaction triggers!")


# ---------------- LIST REACTIONS ----------------
@app.on_message(filters.command(["reactlist"]) & SUDOERS)
async def react_list(_, message: Message):
    if not custom_mentions:
        return await message.reply_text("No reaction triggers found.")
    text = "**🎯 Reaction Triggers:**\n"
    for i, t in enumerate(custom_mentions, start=1):
        text += f"`{i}.` `{t}`\n"
    await message.reply_text(text)


# ---------------- AUTO REACTION HANDLER ----------------
@app.on_message((filters.text | filters.caption))
async def react_on_mentions(_, message: Message):
    try:
        # Skip reacting to bot commands
        if message.text and message.text.startswith("/"):
            return

        text = (message.text or message.caption or "").lower()
        entities = (message.entities or []) + (message.caption_entities or [])
        usernames, user_ids = set(), set()

        # Extract mention usernames and IDs
        for ent in entities:
            if ent.type == "mention":
                uname = (message.text or message.caption)[ent.offset:ent.offset + ent.length].lstrip("@").lower()
                usernames.add(uname)
            elif ent.type == "text_mention" and ent.user:
                user_ids.add(str(ent.user.id))
                if ent.user.username:
                    usernames.add(ent.user.username.lower())

        # Match username triggers
        for uname in usernames:
            if uname in custom_mentions or f"@{uname}" in text:
                emoji = next_emoji()
                await message.react(emoji)
                print(f"[React] {emoji} → @{uname}")
                return

        # Match user ID triggers
        for uid in user_ids:
            if uid in custom_mentions:
                emoji = next_emoji()
                await message.react(emoji)
                print(f"[React] {emoji} → user_id:{uid}")
                return

        # Match keyword triggers
        for trig in custom_mentions:
            if trig in text or f"@{trig}" in text:
                emoji = next_emoji()
                await message.react(emoji)
                print(f"[React] {emoji} → trigger:{trig}")
                return

    except Exception as e:
        print(f"[react_on_mentions] Error: {e}")
