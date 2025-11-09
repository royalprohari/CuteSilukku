from VIPMUSIC import app
from pyrogram import filters

print("[ZZZ-Test] Plugin loaded!")

@app.on_message(filters.command("zzztest") & filters.group)
async def zzz(_, message):
    print("[ZZZ-Test] /zzztest command triggered!")
    await message.reply_text("✅ zzztest works!")
