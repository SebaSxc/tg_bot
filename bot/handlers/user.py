from datetime import datetime, timedelta
from ..state import appointment_times, appointments, blocked_dates, prune_expired_appointments, save_state, user_names
from ..config import TEACHER_ID

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from ..helpers import (
    format_slot,
    format_slot_list,
    get_available_dates,
    get_slot_datetime,
    get_slots_for_date,
    parse_slot,
)
from ..state import appointment_times, appointments, prune_expired_appointments, save_state, user_names
from .common import main_menu

from telegram.error import BadRequest


async def safe_answer(query, *args, **kwargs):
    """Безопасный ответ на callback query без падения по таймауту."""
    try:
        await query.answer(*args, **kwargs)
    except BadRequest:
        pass


def get_booked_slots():
    return {slot for slots in appointments.values() for slot in slots}


def build_day_keyboard(callback_prefix: str, include_back_to: str) -> InlineKeyboardMarkup:
    dates = get_available_dates()
    keyboard = []
    row = []

    for date_key, label in dates:
        # Пропускаем даты, закрытые админом
        if date_key in blocked_dates:
            continue

        row.append(InlineKeyboardButton(label, callback_data=f"{callback_prefix}{date_key}"))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data=include_back_to)])
    return InlineKeyboardMarkup(keyboard)


def build_time_keyboard(date_str: str, callback_prefix: str, include_back_to: str, available_times: list) -> InlineKeyboardMarkup:
    """Генерирует сетку временных интервалов по 2 в ряд."""
    keyboard = []
    row = []

    for time_range in available_times:
        row.append(InlineKeyboardButton(time_range, callback_data=f"{callback_prefix}{date_str}#{time_range}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data=include_back_to)])
    return InlineKeyboardMarkup(keyboard)


async def signup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "📅 Выберите день для записи (на ближайший месяц):",
        reply_markup=build_day_keyboard("day_", "main_menu"),
    )


async def select_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    date_str = query.data.removeprefix("day_")
    prune_expired_appointments(persist=True)

    day_slots = get_slots_for_date(date_str)
    booked = get_booked_slots()
    free_slots = [t for t in day_slots if f"{date_str}_{t}" not in booked]

    if not free_slots:
        await query.answer("На эту дату нет свободных слотов!", show_alert=True)
        return

    await query.answer()
    await query.message.reply_text(
        f"📅 Выбрана дата: <b>{date_str}</b>\nВыберите свободное время:",
        parse_mode="HTML",
        reply_markup=build_time_keyboard(date_str, "time_", "signup", free_slots),
    )


async def select_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    raw_payload = query.data.removeprefix("time_")
    date_str, time_range = raw_payload.split("#", 1)
    slot = f"{date_str}_{time_range}"
    user_id = query.from_user.id
    prune_expired_appointments(persist=True)

    booked = get_booked_slots()
    if slot in booked:
        await query.answer("Этот слот уже успели занять! Пожалуйста, выберите другое время.", show_alert=True)
        return

    # Если записывает преподаватель — запрашиваем фамилию/имя ученика
    if user_id == TEACHER_ID:
        context.user_data["admin_booking_slot"] = (slot, date_str, time_range)
        await query.answer()
        await query.message.reply_text(
            f"✍️ Выбран слот: <b>{format_slot(slot, prefix='')}</b>\n\n"
            "Напишите в ответ <b>фамилию и имя</b> ученика для этой записи:",
            parse_mode="HTML",
        )
        return

    # Обычный сценарий для ученика
    if user_id not in user_names:
        await query.message.reply_text("Пожалуйста, сначала отправьте команду /start и представьтесь.")
        await query.answer()
        return

    appointments.setdefault(user_id, []).append(slot)
    appointment_times[slot] = get_slot_datetime(date_str, time_range)
    save_state()

    await query.answer()
    await query.message.reply_text(f"✅ Вы успешно записались на <b>{format_slot(slot, prefix='')}</b>!", parse_mode="HTML")
    await main_menu(update, context)


async def my_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    prune_expired_appointments(persist=True)
    user_id = query.from_user.id
    slots = appointments.get(user_id, [])

    if not slots:
        await query.message.reply_text("У вас пока нет активных записей на занятия.")
        return

    await query.message.reply_text("📌 <b>Ваши записи:</b>\n" + format_slot_list(slots), parse_mode="HTML")
    await main_menu(update, context)


async def change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    prune_expired_appointments(persist=True)
    user_id = query.from_user.id
    slots = appointments.get(user_id, [])

    if not slots:
        await query.message.reply_text("У вас пока нет записей для переноса.")
        return

    keyboard = [
        [InlineKeyboardButton(format_slot(slot, prefix=""), callback_data=f"change_select_{slot}")]
        for slot in slots
    ]
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")])

    await query.message.reply_text(
        "Выберите занятие, которое хотите перенести:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def change_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["old_slot"] = query.data.removeprefix("change_select_")

    await query.message.reply_text(
        "Выберите новый день:",
        reply_markup=build_day_keyboard("change_day_", "main_menu"),
    )


async def change_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    date_str = query.data.removeprefix("change_day_")
    prune_expired_appointments(persist=True)

    old_slot = context.user_data.get("old_slot")
    booked = get_booked_slots()
    if old_slot:
        booked.discard(old_slot)

    day_slots = get_slots_for_date(date_str)
    free_slots = [t for t in day_slots if f"{date_str}_{t}" not in booked]

    if not free_slots:
        await query.message.reply_text("На этот день нет свободного времени.")
        return

    await query.message.reply_text(
        f"📅 Выбрана дата: <b>{date_str}</b>\nВыберите новое время:",
        parse_mode="HTML",
        reply_markup=build_time_keyboard(date_str, "change_new_", "main_menu", free_slots),
    )


async def change_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    prune_expired_appointments(persist=True)

    if user_id not in user_names:
        await query.message.reply_text("Пожалуйста, сначала отправьте команду /start.")
        await query.answer()
        return

    raw_payload = query.data.removeprefix("change_new_")
    date_str, time_range = raw_payload.split("#", 1)
    new_slot = f"{date_str}_{time_range}"
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
        await query.answer("Этот слот уже занят. Выберите другое время.", show_alert=True)
        return

    user_slots.remove(old_slot)
    user_slots.append(new_slot)
    appointment_times.pop(old_slot, None)
    appointment_times[new_slot] = get_slot_datetime(date_str, time_range)
    save_state()

    await query.answer()
    await query.message.reply_text(
        f"✅ Запись перенесена на <b>{format_slot(new_slot, prefix='')}</b>!\n\n📌 <b>Ваши текущие записи:</b>\n" + format_slot_list(user_slots),
        parse_mode="HTML",
    )
    await main_menu(update, context)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    prune_expired_appointments(persist=True)
    user_id = query.from_user.id
    slots = appointments.get(user_id, [])

    if not slots:
        await query.message.reply_text("У вас пока нет записей для отмены.")
        return

    keyboard = [
        [InlineKeyboardButton(format_slot(slot, prefix=""), callback_data=f"cancel_select_{slot}")]
        for slot in slots
    ]
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")])

    await query.message.reply_text(
        "Выберите запись, которую хотите отменить:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def cancel_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    slot = query.data.removeprefix("cancel_select_")
    prune_expired_appointments(persist=True)

    if user_id not in user_names:
        await query.message.reply_text("Пожалуйста, сначала отправьте команду /start.")
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

    text = f"✅ Запись на <b>{format_slot(slot, prefix='')}</b> отменена.\n"
    if user_slots:
        text += "\n📌 <b>Оставшиеся записи:</b>\n" + format_slot_list(user_slots)
    else:
        text += "\nУ вас больше нет активных записей."

    await query.message.reply_text(text, parse_mode="HTML")
    await main_menu(update, context)

    async def save_manual_booking_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if "admin_booking_slot" not in context.user_data:
            return False  # Сообщение не относится к ручной записи, пропускаем к обычному сохранению имени

        student_name = update.message.text.strip()
        slot, date_str, time_range = context.user_data.pop("admin_booking_slot")

        booked = get_booked_slots()
        if slot in booked:
            await update.message.reply_text("❌ Пока вы вводили фамилию, этот слот уже заняли.")
            await main_menu(update, context)
            return True

        # Генерируем уникальный виртуальный ID для записи стороннего ученика (отрицательное число)
        virtual_user_id = -int(datetime.now().timestamp() * 1000)

        user_names[virtual_user_id] = student_name
        appointments.setdefault(virtual_user_id, []).append(slot)
        appointment_times[slot] = get_slot_datetime(date_str, time_range)
        save_state()

        await update.message.reply_text(
            f"✅ Ученик <b>{student_name}</b> успешно записан на <b>{format_slot(slot, prefix='')}</b>!",
            parse_mode="HTML",
        )
        await main_menu(update, context)
        return True