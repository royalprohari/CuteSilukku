import re
import aiosqlite
import asyncio
from typing import List, Tuple

from pyrogram import filters, errors
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions, Message

from VIPMUSIC import app   # <-- USE MAIN BOT CLIENT
from config import URL_PATTERN

DB_PATH = "biolink_combined.db"

# ------------------ Database helpers ------------------
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS config (
                chat_id INTEGER PRIMARY KEY,
                mode TEXT DEFAULT 'warn',
                limit INTEGER DEFAULT 3,
                penalty TEXT DEFAULT 'mute'
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS warnings (
                chat_id INTEGER,
                user_id INTEGER,
                count INTEGER DEFAULT 0,
                PRIMARY KEY (chat_id, user_id)
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS whitelist (
                chat_id INTEGER,
                user_id INTEGER,
                PRIMARY KEY (chat_id, user_id)
            )
            """
        )
        await db.commit()

# Ensure DB initializes on import/start
@app.on_startup()
async def startup_db(client, *args):
    await init_db()


# ---------- DB API (same names as original biolinkdb expected) ----------
async def get_config(chat_id: int) -> Tuple[str, int, str]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT mode, limit, penalty FROM config WHERE chat_id = ?", (chat_id,))
        row = await cur.fetchone()
        if row:
            return row[0], row[1], row[2]
        # create default
        await db.execute("INSERT OR REPLACE INTO config(chat_id, mode, limit, penalty) VALUES (?, 'warn', 3, 'mute')", (chat_id,))
        await db.commit()
        return 'warn', 3, 'mute'

async def update_config(chat_id: int, mode=None, limit=None, penalty=None):
    cur_mode, cur_limit, cur_penalty = await get_config(chat_id)
    mode = mode or cur_mode
    limit = cur_limit if limit is None else limit
    penalty = penalty or cur_penalty
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO config(chat_id, mode, limit, penalty) VALUES (?, ?, ?, ?)", (chat_id, mode, limit, penalty))
        await db.commit()

async def increment_warning(chat_id: int, user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT count FROM warnings WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
        row = await cur.fetchone()
        if row:
            new = row[0] + 1
            await db.execute("UPDATE warnings SET count = ? WHERE chat_id = ? AND user_id = ?", (new, chat_id, user_id))
        else:
            new = 1
            await db.execute("INSERT INTO warnings(chat_id, user_id, count) VALUES (?, ?, 1)", (chat_id, user_id))
        await db.commit()
        return new

async def reset_warnings(chat_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM warnings WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
        await db.commit()

async def is_whitelisted(chat_id: int, user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT 1 FROM whitelist WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
        return bool(await cur.fetchone())

async def add_whitelist(chat_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO whitelist(chat_id, user_id) VALUES (?, ?)", (chat_id, user_id))
        await db.commit()

async def remove_whitelist(chat_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM whitelist WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
        await db.commit()

async def get_whitelist(chat_id: int) -> List[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id FROM whitelist WHERE chat_id = ?", (chat_id,))
        rows = await cur.fetchall()
        return [r[0] for r in rows]


# ------------------ Helper utils ------------------
AD_PATTERNS = [
    r"\b(?:free|cheap|discount|buy now|sale)\b",
    r"\b(?:\.com|\.net|\.org|\.xyz|\.site|\.online|\.shop)\b",
]

# URL_PATTERN expected from config - if present, prefer it, else fallback
try:
    URL_RE = URL_PATTERN
except Exception:
    URL_RE = re.compile(r"https?://")

AD_RE = re.compile("(?:" + ")|(?:".join(p.strip('()') for p in AD_PATTERNS) + ")", re.IGNORECASE)


async def is_admin(client: Client, chat_id: int, user_id: int) -> bool:
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False


# ------------------ Admin GUI keyboard builder ------------------
def build_main_keyboard(penalty: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Warn", callback_data="warn")],
        [
            InlineKeyboardButton("🔻 𝐌ʋтɛ ✅" if penalty == "mute" else "Mute", callback_data="mute"),
            InlineKeyboardButton("🔻 𝐁αи ✅" if penalty == "ban" else "Ban", callback_data="ban")
        ],
        [InlineKeyboardButton("Close", callback_data="close")]
    ])


# ------------------ Commands (original names preserved) ------------------
@app.on_message(filters.group & filters.command("config"))
async def configure(client: Client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if not await is_admin(client, chat_id, user_id):
        return

    mode, limit, penalty = await get_config(chat_id)
    keyboard = build_main_keyboard(penalty)
    await client.send_message(chat_id, "**Choose penalty for users with links in bio:**", reply_markup=keyboard)
    try:
        await message.delete()
    except Exception:
        pass


@app.on_message(filters.group & filters.command("free"))
async def command_free(client: Client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if not await is_admin(client, chat_id, user_id):
        return

    if message.reply_to_message:
        target = message.reply_to_message.from_user
    elif len(message.command) > 1:
        arg = message.command[1]
        target = await client.get_users(int(arg) if arg.isdigit() else arg)
    else:
        return await client.send_message(chat_id, "**Reply or use /free user or id to whitelist someone.**")

    await add_whitelist(chat_id, target.id)
    await reset_warnings(chat_id, target.id)

    text = f"**✅ {target.mention} 𝐀ᴅᴅɛᴅ 𝐓σ 𝐖нιтɛƖιƨт**"
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔻 𝐔и𝐖нιтɛƖιƨт 🚫", callback_data=f"unwhitelist_{target.id}"),
            InlineKeyboardButton("🔻 𝐂Ɩσƨɛ 🗑️", callback_data="close")
        ]
    ])
    await client.send_message(chat_id, text, reply_markup=keyboard)


@app.on_message(filters.group & filters.command("unfree"))
async def command_unfree(client: Client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if not await is_admin(client, chat_id, user_id):
        return

    if message.reply_to_message:
        target = message.reply_to_message.from_user
    elif len(message.command) > 1:
        arg = message.command[1]
        target = await client.get_users(int(arg) if arg.isdigit() else arg)
    else:
        return await client.send_message(chat_id, "**Reply or use /unfree user or id to unwhitelist someone.**")

    if await is_whitelisted(chat_id, target.id):
        await remove_whitelist(chat_id, target.id)
        text = f"**🚫 {target.mention} 𝐑ɛмσᴠɛ 𝐓σ 𝐖нιтɛƖιƨт**"
    else:
        text = f"**ℹ️ {target.mention} 𝐈ƨ 𝐍σт 𝐖нιтɛƖιƨт.**"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔻 𝐖нιƖιƨт ✅ ", callback_data=f"whitelist_{target.id}"),
            InlineKeyboardButton("🔻 𝐂Ɩσƨɛ 🗑️", callback_data="close")
        ]
    ])
    await client.send_message(chat_id, text, reply_markup=keyboard)


@app.on_message(filters.group & filters.command("freelist"))
async def command_freelist(client: Client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    if not await is_admin(client, chat_id, user_id):
        return

    ids = await get_whitelist(chat_id)
    if not ids:
        await client.send_message(chat_id, "**⚠️ No users are whitelisted in this group.**")
        return

    text = "**📋 Whitelisted Users:**\n\n"
    for i, uid in enumerate(ids, start=1):
        try:
            user = await client.get_users(uid)
            name = f"{user.first_name}{(' ' + user.last_name) if user.last_name else ''}"
            text += f"{i}: {name} [`{uid}`]\n"
        except Exception:
            text += f"{i}: [User not found] [`{uid}`]\n"

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🗑️ Close", callback_data="close")]])
    await client.send_message(chat_id, text, reply_markup=keyboard)


# ------------------ Callback handler (admin GUI) ------------------
@app.on_callback_query()
async def callback_handler(client: Client, callback_query):
    data = callback_query.data
    chat_id = callback_query.message.chat.id
    user_id = callback_query.from_user.id
    if not await is_admin(client, chat_id, user_id):
        return await callback_query.answer("❌ You are not administrator", show_alert=True)

    if data == "close":
        return await callback_query.message.delete()

    if data == "back":
        mode, limit, penalty = await get_config(chat_id)
        kb = build_main_keyboard(penalty)
        await callback_query.message.edit_text("**Choose penalty for users with links in bio:**", reply_markup=kb)
        return await callback_query.answer()

    if data == "warn":
        _, selected_limit, _ = await get_config(chat_id)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🍏" if selected_limit==0 else "0", callback_data="warn_0"),
             InlineKeyboardButton(f"🍏" if selected_limit==1 else "1", callback_data="warn_1"),
             InlineKeyboardButton(f"🍏" if selected_limit==2 else "2", callback_data="warn_2"),
             InlineKeyboardButton(f"🍏" if selected_limit==3 else "3", callback_data="warn_3"),
             InlineKeyboardButton(f"🍏" if selected_limit==4 else "4", callback_data="warn_4"),
             InlineKeyboardButton(f"🍏" if selected_limit==5 else "5", callback_data="warn_5")],
            [InlineKeyboardButton("Back", callback_data="back"), InlineKeyboardButton("Close", callback_data="close")]
        ])
        return await callback_query.message.edit_text("**Set number of bans/warns:**", reply_markup=kb)

    if data in ["mute", "ban"]:
        await update_config(chat_id, penalty=data)
        mode, limit, penalty = await get_config(chat_id)
        kb = build_main_keyboard(penalty)
        await callback_query.message.edit_text("**Penalty selected**", reply_markup=kb)
        return await callback_query.answer()

    if data.startswith("warn_"):
        count = int(data.split("_")[1])
        await update_config(chat_id, limit=count)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🍏" if count==0 else "0", callback_data="warn_0"),
             InlineKeyboardButton(f"🍏" if count==1 else "1", callback_data="warn_1"),
             InlineKeyboardButton(f"🍏" if count==2 else "2", callback_data="warn_2"),
             InlineKeyboardButton(f"🍏" if count==3 else "3", callback_data="warn_3"),
             InlineKeyboardButton(f"🍏" if count==4 else "4", callback_data="warn_4"),
             InlineKeyboardButton(f"🍏" if count==5 else "5", callback_data="warn_5")],
            [InlineKeyboardButton("Back", callback_data="back"), InlineKeyboardButton("Close", callback_data="close")]
        ])
        await callback_query.message.edit_text(f"**Warning limit set to {count}**", reply_markup=kb)
        return await callback_query.answer()

    if data.startswith(("unmute_", "unban_")):
        action, uid = data.split("_")
        target_id = int(uid)
        user = await client.get_chat(target_id)
        name = f"{user.first_name}{(' ' + user.last_name) if user.last_name else ''}"
        try:
            if action == "unmute":
                await client.restrict_chat_member(chat_id, target_id, ChatPermissions(can_send_messages=True))
            else:
                await client.unban_chat_member(chat_id, target_id)
            await reset_warnings(chat_id, target_id)
            msg = f"**{name} (`{target_id}`) has been {'unmuted' if action=='unmute' else 'unbanned'}**."

            kb = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🔻 𝐖нιƖιƨт ✅", callback_data=f"whitelist_{target_id}"),
                    InlineKeyboardButton("🔻 𝐂Ɩσƨɛ 🔻", callback_data="close")
                ]
            ])
            await callback_query.message.edit_text(msg, reply_markup=kb)
        except errors.ChatAdminRequired:
            await callback_query.message.edit_text(f"I don't have permission to {action} users.")
        return await callback_query.answer()

    if data.startswith("cancel_warn_"):
        target_id = int(data.split("_")[-1])
        await reset_warnings(chat_id, target_id)
        user = await client.get_chat(target_id)
        full_name = f"{user.first_name}{(' ' + user.last_name) if user.last_name else ''}"
        mention = f"[{full_name}](tg://user?id={target_id})"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔻 𝐖нιƖιƨт ✅", callback_data=f"whitelist_{target_id}"),
             InlineKeyboardButton("🔻 𝐂Ɩσƨɛ 🔻", callback_data="close")]
        ])
        await callback_query.message.edit_text(f"**✅ {mention} [`{target_id}`] has no more warnings!**", reply_markup=kb)
        return await callback_query.answer()

    if data.startswith("whitelist_"):
        target_id = int(data.split("_")[1])
        await add_whitelist(chat_id, target_id)
        await reset_warnings(chat_id, target_id)
        user = await client.get_chat(target_id)
        full_name = f"{user.first_name}{(' ' + user.last_name) if user.last_name else ''}"
        mention = f"[{full_name}](tg://user?id={target_id})"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔻 𝐔и𝐖нιтɛƖιƨт 🚫", callback_data=f"unwhitelist_{target_id}"),
             InlineKeyboardButton("🔻 𝐂Ɩσƨɛ 🔻", callback_data="close")]
        ])
        await callback_query.message.edit_text(f"**✅ {mention} [`{target_id}`] has been whitelisted!**", reply_markup=kb)
        return await callback_query.answer()

    if data.startswith("unwhitelist_"):
        target_id = int(data.split("_")[1])
        await remove_whitelist(chat_id, target_id)
        user = await client.get_chat(target_id)
        full_name = f"{user.first_name}{(' ' + user.last_name) if user.last_name else ''}"
        mention = f"[{full_name}](tg://user?id={target_id})"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔻 𝐖нιƖιƨт ✅", callback_data=f"whitelist_{target_id}"),
             InlineKeyboardButton("🔻 𝐂Ɩσƨɛ 🔻", callback_data="close")]
        ])
        await callback_query.message.edit_text(f"**❌ {mention} [`{target_id}`] has been removed from whitelist.**", reply_markup=kb)
        return await callback_query.answer()


# ------------------ Primary bio/link check + anti-ads/anti-bot ------------------
@app.on_message(filters.group)
async def check_bio_and_ads(client: Client, message: Message):
    # This handler preserves original bio-checking logic and adds ad/anti-bot checks
    chat_id = message.chat.id
    if not message.from_user:
        return
    user_id = message.from_user.id

    # Admins or whitelisted are bypassed
    if await is_admin(client, chat_id, user_id) or await is_whitelisted(chat_id, user_id):
        return

    # Fetch the user's profile (bio)
    try:
        user = await client.get_chat(user_id)
    except Exception:
        return

    bio = getattr(user, 'bio', None) or ""
    full_name = f"{user.first_name}{(' ' + user.last_name) if user.last_name else ''}"
    mention = f"[{full_name}](tg://user?id={user_id})"

    # Anti-bio link - original functionality
    if URL_RE.search(bio):
        try:
            await message.delete()
        except errors.MessageDeleteForbidden:
            return await message.reply_text("Remove Your Bio-Link.")

        mode, limit, penalty = await get_config(chat_id)
        if mode == "warn":
            count = await increment_warning(chat_id, user_id)
            warning_text = (
                "**🚨 Warning** 🚨\n\n"
                f"👤 **User:** {mention} `[{user_id}]`\n"
                "❌ **Reason:** URL found in bio\n"
                f"⚠️ **Warning:** {count}/{limit}\n\n"
                "**NOTICE: Remove Link In Your Bio**"
            )
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Cancel Warning ❌", callback_data=f"cancel_warn_{user_id}"),
                 InlineKeyboardButton("Whitelist ✅", callback_data=f"whitelist_{user_id}")],
                [InlineKeyboardButton("Close", callback_data="close")]
            ])
            sent = await message.reply_text(warning_text, reply_markup=keyboard)
            if count >= limit:
                try:
                    if penalty == "mute":
                        await client.restrict_chat_member(chat_id, user_id, ChatPermissions())
                        kb = InlineKeyboardMarkup([[InlineKeyboardButton("Unmute", callback_data=f"unmute_{user_id}")]])
                        await sent.edit_text(f"**{full_name} has been muted for [Link In Bio].**", reply_markup=kb)
                    else:
                        await client.ban_chat_member(chat_id, user_id)
                        kb = InlineKeyboardMarkup([[InlineKeyboardButton("Unban", callback_data=f"unban_{user_id}")]])
                        await sent.edit_text(f"**{full_name} has been banned for [Link In Bio].**", reply_markup=kb)
                except errors.ChatAdminRequired:
                    await sent.edit_text(f"**Remove your bio link. I don't have permission to {penalty}.**")
        else:
            # direct punish modes
            try:
                if mode == "mute":
                    await client.restrict_chat_member(chat_id, user_id, ChatPermissions())
                    kb = InlineKeyboardMarkup([[InlineKeyboardButton("Unmute", callback_data=f"unmute_{user_id}")]])
                    await message.reply_text(f"{full_name} has been muted for [Link In Bio].", reply_markup=kb)
                else:
                    await client.ban_chat_member(chat_id, user_id)
                    kb = InlineKeyboardMarkup([[InlineKeyboardButton("Unban", callback_data=f"unban_{user_id}")]])
                    await message.reply_text(f"{full_name} has been banned for [Link In Bio].", reply_markup=kb)
            except errors.ChatAdminRequired:
                return await message.reply_text(f"I don't have permission to {mode} users.")
        return

    # Anti-ads - check message content for ad patterns
    text = (message.text or message.caption or "")
    if AD_RE.search(text):
        # treat as link/advertisement: delete message and warn
        try:
            await message.delete()
        except errors.MessageDeleteForbidden:
            return

        mode, limit, penalty = await get_config(chat_id)
        # use same warn logic but with different reason
        if mode == "warn":
            count = await increment_warning(chat_id, user_id)
            await message.reply_text(f"⚠️ {mention} Advertising detected. Warning {count}/{limit}.")
            if count >= limit:
                try:
                    if penalty == "mute":
                        await client.restrict_chat_member(chat_id, user_id, ChatPermissions())
                        await message.reply_text(f"{full_name} muted for advertising.")
                    else:
                        await client.ban_chat_member(chat_id, user_id)
                        await message.reply_text(f"{full_name} banned for advertising.")
                except errors.ChatAdminRequired:
                    await message.reply_text(f"I don't have permission to {penalty} users.")
                await reset_warnings(chat_id, user_id)
        else:
            try:
                if mode == "mute":
                    await client.restrict_chat_member(chat_id, user_id, ChatPermissions())
                    await message.reply_text(f"{full_name} muted for advertising.")
                else:
                    await client.ban_chat_member(chat_id, user_id)
                    await message.reply_text(f"{full_name} banned for advertising.")
            except errors.ChatAdminRequired:
                await message.reply_text(f"I don't have permission to {mode} users.")
        return

    # Anti-bot / join-protection: if a new user posts immediately with links/ads
    # (we treat recent accounts or messages that contain links as suspicious)
    if message.new_chat_members:
        for new in message.new_chat_members:
            # simple heuristic: account created recently -> cannot fetch easily via API here
            # but we can enforce automatic deletion if new member sends links in their first message
            pass


# ------------------ Extra anti-spam simple handler ------------------
# This is a simple per-user per-chat message counter in-memory for short period
# to detect floods. It's lightweight and will reset on restart.

_spam_cache = {}
_SPAM_WINDOW = 7  # seconds
_SPAM_LIMIT = 6

@app.on_message(filters.group)
async def anti_flood_detect(client: Client, message: Message):
    try:
        uid = (message.chat.id, message.from_user.id)
    except Exception:
        return
    now = asyncio.get_event_loop().time()
    entry = _spam_cache.get(uid)
    if not entry:
        _spam_cache[uid] = [now]
        return
    # prune old timestamps
    entry = [t for t in entry if now - t <= _SPAM_WINDOW]
    entry.append(now)
    _spam_cache[uid] = entry
    if len(entry) > _SPAM_LIMIT:
        # take action: warn or mute depending on config
        chat_id = message.chat.id
        user_id = message.from_user.id
        if await is_admin(client, chat_id, user_id) or await is_whitelisted(chat_id, user_id):
            return
        mode, limit, penalty = await get_config(chat_id)
        if mode == "warn":
            count = await increment_warning(chat_id, user_id)
            await message.reply_text(f"⚠️ Flood detected. Warning {count}/{limit}.")
            if count >= limit:
                try:
                    if penalty == "mute":
                        await client.restrict_chat_member(chat_id, user_id, ChatPermissions())
                        await message.reply_text("User muted for flooding.")
                    else:
                        await client.ban_chat_member(chat_id, user_id)
                        await message.reply_text("User banned for flooding.")
                except errors.ChatAdminRequired:
                    await message.reply_text(f"I don't have permission to {penalty} users.")
                await reset_warnings(chat_id, user_id)
        else:
            try:
                if mode == "mute":
                    await client.restrict_chat_member(chat_id, user_id, ChatPermissions())
                    await message.reply_text("User muted for flooding.")
                else:
                    await client.ban_chat_member(chat_id, user_id)
                    await message.reply_text("User banned for flooding.")
            except errors.ChatAdminRequired:
                await message.reply_text(f"I don't have permission to {mode} users.")
        # clear cache for that user to avoid repeated actions
        _spam_cache.pop(uid, None)

"""
# ------------------ Run bot (when executed directly) ------------------
if __name__ == '__main__':
    print("Starting BioLinkRobot plugin...")
    app.run()
"""
