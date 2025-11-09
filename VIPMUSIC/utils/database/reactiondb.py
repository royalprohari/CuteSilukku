import json
import os

# Local JSON file for storing chat reaction states
DB_PATH = os.path.join(os.getcwd(), "reaction_state.json")


def _load():
    """Load the JSON data from file."""
    if not os.path.exists(DB_PATH):
        return {}
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data: dict):
    """Save the JSON data to file."""
    try:
        with open(DB_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"[ReactionDB] Failed to save data: {e}")


def get_reaction_status(chat_id: int) -> bool:
    """
    Get the reaction status for a chat.
    Returns True if reactions are ON, False otherwise.
    Default is True.
    """
    data = _load()
    return data.get(str(chat_id), True)


def set_reaction_status(chat_id: int, status: bool):
    """
    Set the reaction status for a chat.
    True = Reactions ON, False = Reactions OFF
    """
    data = _load()
    data[str(chat_id)] = status
    _save(data)
    print(f"[ReactionDB] Chat {chat_id} -> {'ENABLED' if status else 'DISABLED'}")
