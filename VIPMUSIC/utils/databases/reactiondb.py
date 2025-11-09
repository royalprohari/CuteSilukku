# VIPMUSIC/utils/databases/reactiondb.py
from VIPMUSIC.core.mongo import mongodb

# MongoDB collection
reaction_statusdb = mongodb.reactionstatus

# Memory cache: {chat_id: True/False}
reaction_enabled = {}

# --- Check if reaction is ON for a chat ---
async def is_reaction_on(chat_id: int) -> bool:
    """
    Returns True if reactions are enabled for the chat
    """
    if chat_id in reaction_enabled:
        return reaction_enabled[chat_id]

    # Fetch from DB
    doc = await reaction_statusdb.find_one({"chat_id": chat_id})
    if doc is None:
        reaction_enabled[chat_id] = True
        return True

    reaction_enabled[chat_id] = False
    return False

# --- Enable reactions ---
async def reaction_on(chat_id: int):
    """
    Enable reactions for a chat
    """
    reaction_enabled[chat_id] = True
    # Remove any existing record (since missing = enabled)
    await reaction_statusdb.delete_one({"chat_id": chat_id})

# --- Disable reactions ---
async def reaction_off(chat_id: int):
    """
    Disable reactions for a chat
    """
    reaction_enabled[chat_id] = False
    # Insert record if not exists
    doc = await reaction_statusdb.find_one({"chat_id": chat_id})
    if doc is None:
        await reaction_statusdb.insert_one({"chat_id": chat_id})
