from VIPMUSIC import app
from pyrogram import filters

print("[ReactionBot] Plugin loaded!")

@app.on_message(filters.command("reactiontest") & filters.group)
async def test_react_cmd(_, message):
    try:
        print("[ReactionBot] /reactiontest triggered")
        await message.reply_text("✅ Reaction test command works!")
    except Exception as e:
        print(f"[ReactionBot ERROR] {e}")
