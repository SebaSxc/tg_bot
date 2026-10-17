import os
from pathlib import Path

env_file = Path(__file__).resolve().parent.parent / ".env"
if env_file.exists():
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip().strip('"').strip("'")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TEACHER_ID = int(os.getenv("TEACHER_ID", "6158059440"))
DATA_FILE = Path(__file__).resolve().parent.parent / "bot_state.json"

# Слоты с 07:00 до 19:00 (крайний слот: 18:00-19:00)
BASE_DAILY_SLOTS = [
    f"{hour:02d}:00-{(hour + 1):02d}:00" for hour in range(7, 19)
]

# На сколько дней вперед формировать график (30 дней = месяц)
DAYS_AHEAD = 30

RUSSIAN_WEEKDAYS = {
    0: "Пн",
    1: "Вт",
    2: "Ср",
    3: "Чт",
    4: "Пт",
    5: "Сб",
    6: "Вс",
}

RUSSIAN_MONTHS = {
    1: "янв",
    2: "фев",
    3: "мар",
    4: "апр",
    5: "мая",
    6: "июн",
    7: "июл",
    8: "авг",
    9: "сен",
    10: "окт",
    11: "ноя",
    12: "дек",
}