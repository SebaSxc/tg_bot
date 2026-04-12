import os
from pathlib import Path

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TEACHER_ID = int(os.getenv("TEACHER_ID", "6158059440"))
DATA_FILE = Path(__file__).resolve().parent.parent / "bot_state.json"

TIME_SLOTS = {
    "tue": ["16:00-17:00", "17:00-18:00", "18:00-19:00", "19:00-20:00"],
    "wed": ["16:00-17:00", "17:00-18:00", "18:00-19:00", "19:00-20:00"],
    "thu": ["16:00-17:00", "17:00-18:00", "18:00-19:00", "19:00-20:00"],
    "fri": ["16:00-17:00", "17:00-18:00", "18:00-19:00", "19:00-20:00"],
}

DAY_NAMES = {
    "tue": "Вторник",
    "wed": "Среда",
    "thu": "Четверг",
    "fri": "Пятница",
}
