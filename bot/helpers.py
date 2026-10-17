from datetime import datetime, timedelta
from html import escape

from .config import BASE_DAILY_SLOTS, DAYS_AHEAD, RUSSIAN_MONTHS, RUSSIAN_WEEKDAYS
from .state import user_names


def parse_slot(slot: str):
    return slot.split("_", 1)


def format_slot(slot: str, prefix: str = "- ") -> str:
    date_str, time_range = parse_slot(slot)
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    month_name = RUSSIAN_MONTHS[dt.month]
    weekday_name = RUSSIAN_WEEKDAYS[dt.weekday()]
    return f"{prefix}{dt.day} {month_name} ({weekday_name}) {time_range}"


def format_slot_list(slots, prefix: str = "- ") -> str:
    return "\n".join(format_slot(slot, prefix=prefix) for slot in slots)


def get_slot_datetime(date_str: str, time_range: str) -> datetime:
    start_str = time_range.split("-", 1)[0]
    hour, minute = map(int, start_str.split(":"))
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return datetime(dt.year, dt.month, dt.day, hour, minute)


def get_available_dates(days_count: int = DAYS_AHEAD) -> list[tuple[str, str]]:
    """Возвращает список пар (строка_даты_YYYY-MM-DD, читаемая_метка) на месяц вперед."""
    now = datetime.now()
    dates = []
    for i in range(days_count):
        day = now + timedelta(days=i)
        date_key = day.strftime("%Y-%m-%d")
        label = f"{day.day} {RUSSIAN_MONTHS[day.month]} ({RUSSIAN_WEEKDAYS[day.weekday()]})"
        dates.append((date_key, label))
    return dates


def get_slots_for_date(date_str: str) -> list[str]:
    """Возвращает список временных слотов для даты, отсекая прошедшие часы на сегодня."""
    now = datetime.now()
    available = []
    for slot in BASE_DAILY_SLOTS:
        slot_dt = get_slot_datetime(date_str, slot)
        if slot_dt > now:
            available.append(slot)
    return available


def format_user_label(user_id: int) -> str:
    display_name = escape(user_names.get(user_id, f"ID {user_id}"))
    if user_id in user_names:
        return f'<a href="tg://user?id={user_id}">{display_name}</a>'
    return display_name