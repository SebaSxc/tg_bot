import json
from datetime import datetime

from .config import DATA_FILE

appointments = {}
appointment_times = {}
user_names = {}


def save_state():
    payload = {
        "appointments": {str(user_id): slots for user_id, slots in appointments.items()},
        "appointment_times": {slot: slot_time.isoformat() for slot, slot_time in appointment_times.items()},
        "user_names": {str(user_id): name for user_id, name in user_names.items()},
    }
    DATA_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def prune_expired_appointments(now=None, persist=False):
    current_time = now or datetime.now()
    known_slots = {slot for slots in appointments.values() for slot in slots}
    expired_slots = {
        slot for slot in known_slots
        if appointment_times.get(slot) is None or appointment_times[slot] <= current_time
    }

    if not expired_slots:
        return False

    for slot in expired_slots:
        appointment_times.pop(slot, None)

    for user_id, slots in list(appointments.items()):
        remaining_slots = [slot for slot in slots if slot not in expired_slots]
        if remaining_slots:
            appointments[user_id] = remaining_slots
        else:
            appointments.pop(user_id, None)

    if persist:
        save_state()

    return True


def load_state():
    if not DATA_FILE.exists():
        return

    try:
        payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Не удалось загрузить состояние бота: {exc}")
        return

    appointments.clear()
    appointment_times.clear()
    user_names.clear()

    raw_appointments = payload.get("appointments", {})
    if isinstance(raw_appointments, dict):
        for user_id, slots in raw_appointments.items():
            try:
                parsed_user_id = int(user_id)
            except (TypeError, ValueError):
                continue

            if isinstance(slots, list):
                appointments[parsed_user_id] = [slot for slot in slots if isinstance(slot, str)]

    raw_appointment_times = payload.get("appointment_times", {})
    if isinstance(raw_appointment_times, dict):
        for slot, slot_time in raw_appointment_times.items():
            try:
                appointment_times[slot] = datetime.fromisoformat(slot_time)
            except (TypeError, ValueError):
                continue

    raw_user_names = payload.get("user_names", {})
    if isinstance(raw_user_names, dict):
        for user_id, name in raw_user_names.items():
            try:
                parsed_user_id = int(user_id)
            except (TypeError, ValueError):
                continue

            user_names[parsed_user_id] = str(name).strip()

    prune_expired_appointments(persist=True)
