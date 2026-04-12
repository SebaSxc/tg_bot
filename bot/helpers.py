from datetime import datetime, timedelta
from html import escape

from .config import DAY_NAMES
from .state import user_names


def parse_slot(slot):
    return slot.split("_", 1)


def format_slot(slot, prefix="- "):
    day, time = parse_slot(slot)
    return f"{prefix}{DAY_NAMES[day]} {time}"


def format_slot_list(slots, prefix="- "):
    return "\n".join(format_slot(slot, prefix=prefix) for slot in slots)


def get_slot_datetime(day, time_range):
    today = datetime.today()
    weekday_map = {"tue": 1, "wed": 2, "thu": 3, "fri": 4}

    start_str = time_range.split("-", 1)[0]
    hour_part, minute_part = start_str.split(":")
    hour = int(hour_part)
    minute = int(minute_part)

    days_ahead = (weekday_map[day] - today.weekday()) % 7
    slot_date = (today + timedelta(days=days_ahead)).date()
    slot_datetime = datetime(slot_date.year, slot_date.month, slot_date.day, hour, minute, 0, 0)

    if days_ahead == 0 and slot_datetime <= today:
        slot_datetime += timedelta(days=7)

    return slot_datetime


def format_user_label(user_id):
    display_name = escape(user_names.get(user_id, f"ID {user_id}"))
    if user_id in user_names:
        return f'<a href="tg://user?id={user_id}">{display_name}</a>'
    return display_name
