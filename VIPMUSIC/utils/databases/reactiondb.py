# VIPMUSIC/utils/databases/reactiondb.py

import json
import os
from typing import Dict

# Path to JSON file for reaction status
REACTION_FILE = os.path.join(os.path.dirname(__file__), "reaction_status.json")

# Ensure file exists
if not os.path.exists(REACTION_FILE):
    with open(REACTION_FILE, "w") as f:
        json.dump({}, f)


def load_reaction_data() -> Dict[str, bool]:
    """Load all chat reaction statuses from JSON."""
    try:
        with open(REACTION_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_reaction_data(data: Dict[str, bool]):
    """Save all chat reaction statuses to JSON."""
    with open(REACTION_FILE, "w") as f:
        json.dump(data, f, indent=4)


def get_reaction_status(chat_id: int) -> bool:
    """Return True if reactions are enabled for this chat."""
    data = load_reaction_data()
    return str(chat_id) in data and data[str(chat_id)]


def set_reaction_status(chat_id: int, status: bool):
    """Enable or disable reaction for this chat."""
    data = load_reaction_data()
    data[str(chat_id)] = status
    save_reaction_data(data)
