# VIPMUSIC/utils/databases/reactiondb.py
# Persist per-chat reaction enabled/disabled state using MongoDB
# and keep an in-memory cache for fast checks.

from VIPMUSIC.core.mongo import mongodb

# Collection name
reaction_statusdb = mongodb["reactionstatus"]

# In-memory cache: {chat_id: bool}
# True => reactions are ON for chat
# False => reactions are OFF for chat
reaction_enabled = {}

async def load_all_statuses():
    """
    Load all stored OFF statuses into memory on startup.
    NOTE: DB stores only OFF documents (missing doc => enabled).
    """
    cursor = reaction_statusdb.find({})
    docs = await cursor.to_list(length=None)
    # If a doc exists, it means reactions are OFF for that chat
    for d in docs:
        chat_id = d.get("chat_id")
        if chat_id is not None:
            reaction_enabled[int(chat_id)] = False

async def is_reaction_on(chat_id: int) -> bool:
    """
    Returns True if reactions are enabled for chat_id.
    Missing DB doc means enabled (default ON).
    """
    if chat_id in reaction_enabled:
        return reaction_enabled[chat_id]

    # check DB
    doc = await reaction_statusdb.find_one({"chat_id": chat_id})
    if doc is None:
        reaction_enabled[chat_id] = True
        return True

    reaction_enabled[chat_id] = False
    return False

async def reaction_on(chat_id: int):
    """
    Enable reactions for a chat: remove any OFF record and set cache True.
    """
    reaction_enabled[chat_id] = True
    await reaction_statusdb.delete_one({"chat_id": chat_id})

async def reaction_off(chat_id: int):
    """
    Disable reactions for a chat: insert OFF record if not exists and set cache False.
    """
    reaction_enabled[chat_id] = False
    # insert a marker document if missing
    doc = await reaction_statusdb.find_one({"chat_id": chat_id})
    if doc is None:
        await reaction_statusdb.insert_one({"chat_id": chat_id})
