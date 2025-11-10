import asyncio
from VIPMUSIC.misc import SUDOERS
from VIPMUSIC.core.userbot import Userbot
from pyrogram import Client, filters
from pyrogram.errors import UserAlreadyParticipant
from VIPMUSIC import app
import asyncio
import random
from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import (
    ChatAdminRequired,
    InviteRequestSent,
    UserAlreadyParticipant,
    UserNotParticipant,
)
from VIPMUSIC import app
from VIPMUSIC.utils.vip_ban import admin_filter
from VIPMUSIC.utils.decorators.userbotjoin import UserbotWrapper
from VIPMUSIC.utils.database import get_assistant, is_active_chat
links = {}

print("[userbotjoin] userbotjoin, leaveuserbot")

@app.on_message(filters.group & filters.command(["userbotjoin", f"userbotjoin@{app.username}"]) & ~filters.private)
async def join_group(client, message):
    chat_id = message.chat.id
    userbot = await get_assistant(message.chat.id)
    userbot_id = userbot.id
    done = await message.reply("**🤧🦋 𝑊𝑎𝑖𝑡 𝑃𝑎𝑛𝑛𝑢𝑔𝑎 𝐷𝑎  𝐴𝑠𝑠𝑖𝑠𝑡𝑎𝑛𝑡 🐣✨**...")
    await asyncio.sleep(1)
    # Get chat member object
    chat_member = await app.get_chat_member(chat_id, app.id)
    
    # Condition 1: Group username is present, bot is not admin
    if message.chat.username and not chat_member.status == ChatMemberStatus.ADMINISTRATOR:
        try:
            await userbot.join_chat(message.chat.username)
            await done.edit_text("**🫳🏻🐣 𝐴𝑠𝑠𝑖𝑠𝑡𝑎𝑛𝑡 𝑉𝑎𝑛𝑡ℎ𝑒𝑎𝑛 𝑚𝑎𝑚𝑒𝑎 🫂💫**")
        except Exception as e:
            await done.edit_text("**𝐴𝑑𝑚𝑖𝑛 𝑃𝑜𝑑𝑢 𝐷𝑎 𝑚𝑎𝑛𝑔𝑎 🙄✨**")
            

    # Condition 2: Group username is present, bot is admin, and Userbot is not banned
    if message.chat.username and chat_member.status == ChatMemberStatus.ADMINISTRATOR:
        try:
            await userbot.join_chat(message.chat.username)
            await done.edit_text("**🫳🏻🐣 𝐴𝑠𝑠𝑖𝑠𝑡𝑎𝑛𝑡 𝑉𝑎𝑛𝑡ℎ𝑒𝑎𝑛 𝑚𝑎𝑚𝑒𝑎 🫂💫**")
        except Exception as e:
            await done.edit_text(str(e))

    
    
    # Condition 3: Group username is not present/group is private, bot is admin and Userbot is banned
    if message.chat.username and chat_member.status == ChatMemberStatus.ADMINISTRATOR:
        userbot_member = await app.get_chat_member(chat_id, userbot.id)
        if userbot_member.status in [ChatMemberStatus.BANNED, ChatMemberStatus.RESTRICTED]:
            try:
                await app.unban_chat_member(chat_id, userbot.id)
                await done.edit_text("**✨🐣 𝑂𝑟𝑢 𝑣𝑎𝑙𝑖𝑦𝑎 𝑉𝑎𝑙𝑖𝑦𝑎 𝑈𝑛𝑏𝑎𝑛 𝑃𝑎𝑛𝑛𝑖𝑡ℎ𝑎𝑛𝑔𝑎 🫂💫🫀**")
                await userbot.join_chat(message.chat.username)
                await done.edit_text("**𝑈𝑛𝑏𝑎𝑛 𝑃𝑎𝑛𝑛𝑖𝑦𝑎𝑐ℎ𝑢 𝐷𝑒𝑖 𝐴𝑑𝑚𝑖𝑛𝑢𝑢 𝑁𝑎𝑙𝑙𝑎 𝑖𝑟𝑢𝑝𝑎 𝑝𝑜𝑑𝑎 🥹🤌🏻**")
            except Exception as e:
                await done.edit_text("**𝐵𝑎𝑛 𝑃𝑒𝑟𝑚𝑖𝑠𝑠𝑖𝑜𝑛 𝐾𝑢𝑑𝑢𝑛𝑔𝑎 𝑑𝑎 𝐴𝑑𝑚𝑖𝑛𝑢𝑢𝑢 🤌🏻✨ 𝑒𝑛 𝑝𝑎𝑛𝑔𝑎𝑙𝑖𝑦𝑎 𝑁𝑎𝑛𝑒𝑎 𝑈𝑛𝑎𝑏𝑎𝑛 𝑃𝑎𝑛𝑛𝑖𝑘𝑎𝑟𝑒𝑎𝑛 🥹🫀/userbotjoin**")
        return
    
    # Condition 4: Group username is not present/group is private, bot is not admin
    if not message.chat.username and not chat_member.status == ChatMemberStatus.ADMINISTRATOR:
        await done.edit_text("**𝐴𝑑𝑚𝑖𝑛 𝑃𝑜𝑑𝑢 𝐷𝑎 𝑚𝑎𝑛𝑔𝑎 🙄✨.**")
        


    # Condition 5: Group username is not present/group is private, bot is admin
    if not message.chat.username and chat_member.status == ChatMemberStatus.ADMINISTRATOR:
        try:
            try:
                userbot_member = await app.get_chat_member(chat_id, userbot.id)
                if userbot_member.status not in [ChatMemberStatus.BANNED, ChatMemberStatus.RESTRICTED]:
                    await done.edit_text("*🫳🏻🐣 𝐴𝑠𝑠𝑖𝑠𝑡𝑎𝑛𝑡 𝑉𝑎𝑛𝑡ℎ𝑒𝑎𝑛 𝑚𝑎𝑚𝑒𝑎 🫂💫.**")
                    return
            except Exception as e:
                await done.edit_text("**𝑊𝑎𝑖𝑡 𝑃𝑎𝑛𝑛𝑢 𝑑𝑎 𝑉𝑎𝑟𝑢𝑣𝑒𝑎𝑛 🚶🏻‍♂🫴🏻💙**.")
                await done.edit_text("**𝑊𝑎𝑖𝑡 𝑃𝑎𝑛𝑛𝑢 𝑑𝑎 𝑉𝑎𝑟𝑢𝑣𝑒𝑎𝑛 🚶🏻‍♂🫴🏻💙**...")
                invite_link = await app.create_chat_invite_link(chat_id, expire_date=None)
                await asyncio.sleep(2)
                await userbot.join_chat(invite_link.invite_link)
                await done.edit_text("**🫳🏻🐣 𝐴𝑠𝑠𝑖𝑠𝑡𝑎𝑛𝑡 𝑉𝑎𝑛𝑡ℎ𝑒𝑎𝑛 𝑚𝑎𝑚𝑒𝑎 🫂💫**")
        except Exception as e:
            await done.edit_text(f"**𝐴𝑑𝑚𝑖𝑛 𝑃𝑜𝑑𝑢 𝐷𝑎 𝑚𝑎𝑛𝑔𝑎 🙄✨ /userbotjoin.**\n\n**➥ ɪᴅ »** @{userbot.username}")

    
    
    # Condition 6: Group username is not present/group is private, bot is admin and Userbot is banned
    if not message.chat.username and chat_member.status == ChatMemberStatus.ADMINISTRATOR:
        userbot_member = await app.get_chat_member(chat_id, userbot.id)
        if userbot_member.status in [ChatMemberStatus.BANNED, ChatMemberStatus.RESTRICTED]:
            try:
                await app.unban_chat_member(chat_id, userbot.id)
                await done.edit_text("**𝑈𝑛𝑏𝑎𝑛 𝑃𝑎𝑛𝑛𝑖𝑦𝑎𝑐ℎ𝑢 𝐷𝑒𝑖 𝐴𝑑𝑚𝑖𝑛𝑢𝑢 𝑁𝑎𝑙𝑙𝑎 𝑖𝑟𝑢𝑝𝑎 𝑝𝑜𝑑𝑎 🥹🤌🏻**\n**ᴛʏᴘᴇ ᴀɢᴀɪɴ:- /userbotjoin.**")
                invite_link = await app.create_chat_invite_link(chat_id, expire_date=None)
                await asyncio.sleep(2)
                await userbot.join_chat(invite_link.invite_link)
                await done.edit_text("**🐣 𝑂𝑟𝑢𝑣𝑎𝑙𝑖𝑦𝑎 𝑉𝑎𝑙𝑖𝑦𝑎 𝑈𝑛𝑏𝑎𝑛 𝑃𝑎𝑛𝑛𝑖𝑡ℎ𝑎𝑛𝑔𝑎 🫂💫🫀**")
            except Exception as e:
                await done.edit_text(f"**𝐵𝑎𝑛 𝑃𝑒𝑟𝑚𝑖𝑠𝑠𝑖𝑜𝑛 𝐾𝑢𝑑𝑢𝑛𝑔𝑎 𝑑𝑎 𝐴𝑑𝑚𝑖𝑛𝑢𝑢𝑢 🤌🏻✨ 𝑒𝑛 𝑝𝑎𝑛𝑔𝑎𝑙𝑖𝑦𝑎 𝑁𝑎𝑛𝑒𝑎 𝑈𝑛𝑎𝑏𝑎𝑛 𝑃𝑎𝑛𝑛𝑖𝑘𝑎𝑟𝑒𝑎𝑛 🥹🫀 /userbotjoin.**\n\n**💕⚡🍂 ɪᴅ »** @{userbot.username}")
        return
    
    
    


        
@app.on_message(filters.command("userbotleave") & filters.group & admin_filter)
async def leave_one(client, message):
    try:
        userbot = await get_assistant(message.chat.id)
        await userbot.leave_chat(message.chat.id)
        await app.send_message(message.chat.id, "**🤧🤧 𝑃𝑜𝑖𝑡ℎ𝑢 𝑉𝑎 𝑈𝑠𝑒𝑟𝑏𝑜𝑡 𝑃𝑎𝑛𝑔𝑎𝑙𝑖🥹🫀**")
    except Exception as e:
        print(e)


@app.on_message(filters.command(["leaveall", f"leaveall@{app.username}"]) & SUDOERS)
async def leave_all(client, message):
    if message.from_user.id not in SUDOERS:
        return

    left = 0
    failed = 0
    lol = await message.reply("🔄 **ᴜsᴇʀʙᴏᴛ** ʟᴇᴀᴠɪɴɢ ᴀʟʟ ᴄʜᴀᴛs !")
    try:
        userbot = await get_assistant(message.chat.id)
        async for dialog in userbot.get_dialogs():
            if dialog.chat.id == -1001733534088:
                continue
            try:
                await userbot.leave_chat(dialog.chat.id)
                left += 1
                await lol.edit(
                    f"**ᴜsᴇʀʙᴏᴛ ʟᴇᴀᴠɪɴɢ ᴀʟʟ ɢʀᴏᴜᴘ...**\n\n**ʟᴇғᴛ:** {left} ᴄʜᴀᴛs.\n**ғᴀɪʟᴇᴅ:** {failed} ᴄʜᴀᴛs."
                )
            except BaseException:
                failed += 1
                await lol.edit(
                    f"**ᴜsᴇʀʙᴏᴛ ʟᴇᴀᴠɪɴɢ...**\n\n**ʟᴇғᴛ:** {left} chats.\n**ғᴀɪʟᴇᴅ:** {failed} chats."
                )
            await asyncio.sleep(3)
    finally:
        await app.send_message(
            message.chat.id, f"**✅ ʟᴇғᴛ ғʀᴏᴍ:* {left} chats.\n**❌ ғᴀɪʟᴇᴅ ɪɴ:** {failed} chats."
        )
