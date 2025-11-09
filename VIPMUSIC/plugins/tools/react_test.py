from VIPMUSIC import app
from pyrogram import filters

print("[ReactionBot] Plugin loaded!")

@app.on_message(filters.command("reactiontest") & filters.chat.type.in_({"group", "supergroup"}))
async def test_react_cmd(_, message):
    print("[ReactionBot] /reactiontest command triggered!")
    await message.reply_text("✅ Reaction test command works!")
