import json
from datetime import datetime
from .config import DATA_FILE

user_names = {}
appointments = {}
appointment_times = {}
blocked_dates = set()


def load_state():
    global user_names, appointments, appointment_times, blocked_dates
    if not DATA_FILE.exists():
        return

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            user_names = {int(k): v for k, v in data.get("user_names", {}).items()}
            appointments = {int(k): v for k, v in data.get("appointments", {}).items()}
            appointment_times = {
                k: datetime.fromisoformat(v) for k, v in data.get("appointment_times", {}).items()
            }
            blocked_dates = set(data.get("blocked_dates", []))
    except Exception:
        pass


def save_state():
    data = {
        "user_names": user_names,
        "appointments": appointments,
        "appointment_times": {k: v.isoformat() for k, v in appointment_times.items()},
        "blocked_dates": list(blocked_dates),
    }
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def prune_expired_appointments(persist=False):
    now = datetime.now()
    expired = [slot for slot, dt in appointment_times.items() if dt <= now]
    if not expired:
        return

    for slot in expired:
        del appointment_times[slot]
        for user_id, slots in list(appointments.items()):
            if slot in slots:
                slots.remove(slot)
                if not slots:
                    del appointments[user_id]

    if persist:
        save_state()