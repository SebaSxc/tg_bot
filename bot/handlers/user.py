from datetime import datetime, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from ..config import DAY_NAMES, TIME_SLOTS
from ..helpers import format_slot, format_slot_list, get_slot_datetime
from ..state import appointment_times, appointments, prune_expired_appointments, save_state, user_names
from .common import main_menu


def get_booked_slots():
    return {slot for slots in appointments.values() for slot in slots}


def build_day_keyboard(callback_prefix, include_back_to):
    keyboard = [
        [InlineKeyboardButton(DAY_NAMES[day], callback_data=f"{callback_prefix}{day}")]
        for day in TIME_SLOTS
    ]
    keyboard.append([InlineKeyboardButton("⬅ Назад", callback_data=include_back_to)])
    return InlineKeyboardMarkup(keyboard)


def build_time_keyboard(day, callback_prefix, include_back_to, available_times):
    keyboard = [
        [InlineKeyboardButton(time_range, callback_data=f"{callback_prefix}{day}_{time_range}")]
        for time_range in available_times
    ]
    keyboard.append([InlineKeyboardButton("⬅ Назад", callback_data=include_back_to)])
    return InlineKeyboardMarkup(keyboard)


async def signup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "Выбери день:",
        reply_markup=build_day_keyboard("day_", "main_menu"),
    )


async def select_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    day = query.data.split("_", 1)[1]
    prune_expired_appointments(persist=True)

    booked = get_booked_slots()
    free_slots = [time_range for time_range in TIME_SLOTS[day] if f"{day}_{time_range}" not in booked]
    if not free_slots:
        await query.answer("Нет свободных мест на этот день!", show_alert=True)
        return

    await query.answer()
    await query.message.reply_text(
        f"Ты выбрал {DAY_NAMES[day]}. Теперь выбери время:",
        reply_markup=build_time_keyboard(day, "time_", "signup", free_slots),
    )


async def select_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, day, time_range = query.data.split("_")
    slot = f"{day}_{time_range}"
    user_id = query.from_user.id
    prune_expired_appointments(persist=True)

    if user_id not in user_names:
        await query.message.reply_text("Пожалуйста, сначала отправь своё имя командой /start.")
        await query.answer()
        return

    booked = get_booked_slots()
    if slot in booked:
        await query.answer("Этот слот уже занят. Выбери другое время.", show_alert=True)
        return

    appointments.setdefault(user_id, []).append(slot)
    appointment_times[slot] = get_slot_datetime(day, time_range)
    save_state()

    await query.answer()
    await query.message.reply_text(f"✅ Ты записался на {DAY_NAMES[day]} {time_range}!")
    await main_menu(update, context)


async def my_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    prune_expired_appointments(persist=True)
    user_id = query.from_user.id
    slots = appointments.get(user_id, [])

    if not slots:
        await query.message.reply_text("Ты пока не записан на занятия.")
        return

    await query.message.reply_text("📌 Твои записи:\n" + format_slot_list(slots))
    await main_menu(update, context)


async def change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    prune_expired_appointments(persist=True)
    user_id = query.from_user.id
    slots = appointments.get(user_id, [])

    if not slots:
        await query.message.reply_text("У тебя пока нет записей.")
        return

    keyboard = [
        [InlineKeyboardButton(format_slot(slot, prefix=""), callback_data=f"change_select_{slot}")]
        for slot in slots
    ]
    keyboard.append([InlineKeyboardButton("⬅ Назад", callback_data="main_menu")])

    await query.message.reply_text(
        "Выбери запись, которую хочешь изменить:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def change_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["old_slot"] = query.data.split("_", 2)[2]

    await query.message.reply_text(
        "Выбери день, на который хочешь перенести запись:",
        reply_markup=build_day_keyboard("change_day_", "main_menu"),
    )


async def change_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    day = query.data.split("_")[2]
    prune_expired_appointments(persist=True)

    old_slot = context.user_data.get("old_slot")
    booked = get_booked_slots()
    if old_slot:
        booked.discard(old_slot)

    free_slots = [time_range for time_range in TIME_SLOTS[day] if f"{day}_{time_range}" not in booked]
    if not free_slots:
        await query.message.reply_text("Нет доступного времени на этот день.")
        return

    await query.message.reply_text(
        "Выбери новое время:",
        reply_markup=build_time_keyboard(day, "change_new_", "main_menu", free_slots),
    )


async def change_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    prune_expired_appointments(persist=True)

    if user_id not in user_names:
        await query.message.reply_text("Пожалуйста, сначала отправь своё имя командой /start.")
        await query.answer()
        return

    _, _, day, time_range = query.data.split("_")
    new_slot = f"{day}_{time_range}"
    old_slot = context.user_data.get("old_slot")
    user_slots = appointments.get(user_id, [])

    if not old_slot or old_slot not in user_slots:
        await query.answer()
        await query.message.reply_text("Ошибка: старая запись не найдена.")
        return

    booked = get_booked_slots()
    if old_slot:
        booked.discard(old_slot)

    if new_slot in booked:
        await query.answer("Этот слот уже занят. Выбери другое время.", show_alert=True)
        return

    user_slots.remove(old_slot)
    user_slots.append(new_slot)
    appointment_times.pop(old_slot, None)
    appointment_times[new_slot] = get_slot_datetime(day, time_range)
    save_state()

    await query.answer()
    await query.message.reply_text(
        "✅ Запись изменена!\n\n📌 Твои текущие записи:\n" + format_slot_list(user_slots)
    )
    await main_menu(update, context)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    prune_expired_appointments(persist=True)
    user_id = query.from_user.id
    slots = appointments.get(user_id, [])

    if not slots:
        await query.message.reply_text("У тебя пока нет записей для отмены.")
        return

    keyboard = [
        [InlineKeyboardButton(format_slot(slot, prefix=""), callback_data=f"cancel_select_{slot}")]
        for slot in slots
    ]
    keyboard.append([InlineKeyboardButton("⬅ Назад", callback_data="main_menu")])

    await query.message.reply_text(
        "Выбери запись, которую хочешь отменить:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def cancel_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    slot = query.data.split("_", 2)[2]
    prune_expired_appointments(persist=True)

    if user_id not in user_names:
        await query.message.reply_text("Пожалуйста, сначала отправь своё имя командой /start.")
        await query.answer()
        return

    slot_time = appointment_times.get(slot)
    user_slots = appointments.get(user_id, [])
    await query.answer()

    if not slot_time or slot not in user_slots:
        await query.message.reply_text("Запись не найдена.")
        return

    if slot_time - datetime.now() < timedelta(hours=12):
        await query.message.reply_text("❌ До занятия осталось меньше 12 часов. Отмена невозможна.")
        return

    user_slots.remove(slot)
    appointment_times.pop(slot, None)
    save_state()

    text = f"✅ Запись на {format_slot(slot, prefix='')} отменена.\n"
    if user_slots:
        text += "\n📌 Твои оставшиеся записи:\n" + format_slot_list(user_slots)
    else:
        text += "\nУ тебя больше нет записей."

    await query.message.reply_text(text)
    await main_menu(update, context)
