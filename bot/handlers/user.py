import calendar
from datetime import datetime, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from telegram.error import BadRequest

from ..helpers import (
    format_slot,
    format_slot_list,
    get_slot_datetime,
    get_slots_for_date,
)
from ..state import appointment_times, appointments, blocked_dates, prune_expired_appointments, save_state, user_names
from .common import main_menu


async def safe_answer(query, *args, **kwargs):
    try:
        await query.answer(*args, **kwargs)
    except BadRequest:
        pass


def get_booked_slots():
    return {slot for slots in appointments.values() for slot in slots}


def build_calendar(year: int, month: int, callback_prefix: str, include_back_to: str, user_slots: list = None) -> InlineKeyboardMarkup:
    keyboard = []
    month_names = {1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель", 5: "Май", 6: "Июнь",
                   7: "Июль", 8: "Август", 9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"}

    # Строка 1: Месяц и Год
    keyboard.append([InlineKeyboardButton(f"{month_names[month]} {year}", callback_data="ignore")])

    # Строка 2: Дни недели
    week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    keyboard.append([InlineKeyboardButton(day, callback_data="ignore") for day in week_days])

    # Строки 3+: Сетка дней
    cal = calendar.monthcalendar(year, month)
    
    for week in cal:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data="ignore"))
            else:
                date_str = f"{year}-{month:02d}-{day:02d}"
                
                # Обновленная логика отображения
                if date_str in blocked_dates:
                    btn_text = "🔴"  # Только красный круг без числа
                elif user_slots and any(s.startswith(date_str) for s in user_slots):
                    btn_text = f"{day} 🟢"  # Число и зеленый круг
                else:
                    btn_text = str(day)

                row.append(InlineKeyboardButton(btn_text, callback_data=f"{callback_prefix}{date_str}"))
        keyboard.append(row)

    # Навигация по месяцам
    prev_m = month - 1 if month > 1 else 12
    prev_y = year if month > 1 else year - 1
    next_m = month + 1 if month < 12 else 1
    next_y = year if month < 12 else year + 1

    keyboard.append([
        InlineKeyboardButton("⬅️", callback_data=f"cal_nav_{prev_y}_{prev_m}_{callback_prefix}"),
        InlineKeyboardButton("Назад", callback_data=include_back_to),
        InlineKeyboardButton("➡️", callback_data=f"cal_nav_{next_y}_{next_m}_{callback_prefix}")
    ])

    return InlineKeyboardMarkup(keyboard)


def build_time_keyboard(date_str: str, callback_prefix: str, include_back_to: str, all_times: list, booked_times: set) -> InlineKeyboardMarkup:
    keyboard = []
    row = []

    for time_range in all_times:
        if time_range in booked_times:
            btn_text = f"🔒 {time_range}"
        else:
            btn_text = time_range

        row.append(InlineKeyboardButton(btn_text, callback_data=f"{callback_prefix}{date_str}#{time_range}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data=include_back_to)])
    return InlineKeyboardMarkup(keyboard)


async def calendar_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопок перелистывания месяцев."""
    query = update.callback_query
    _, _, year_str, month_str, prefix = query.data.split("_", 4)
    year, month = int(year_str), int(month_str)

    user_id = query.from_user.id
    
    # Для админа собираем вообще все слоты, для ученика — только его личные
    from ..config import TEACHER_ID
    if user_id == TEACHER_ID:
        user_slots = [slot for slots in appointments.values() for slot in slots]
    else:
        user_slots = appointments.get(user_id, [])

    await safe_answer(query)
    try:
        await query.message.edit_reply_markup(
            reply_markup=build_calendar(year, month, prefix, "main_menu", user_slots)
        )
    except BadRequest:
        pass


async def ignore_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Глушит нажатия на пустые ячейки и заголовки календаря."""
    await safe_answer(update.callback_query)


async def signup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
    now = datetime.now()
    user_id = query.from_user.id
    
    from ..config import TEACHER_ID
    if user_id == TEACHER_ID:
        user_slots = [slot for slots in appointments.values() for slot in slots]
        text = "📅 <b>Выберите дату в календаре:</b>\n<i>(🟢 — есть ученики, 🔴 — выходной)</i>"
    else:
        user_slots = appointments.get(user_id, [])
        text = "📅 <b>Выберите дату в календаре:</b>\n<i>(🟢 — ваши записи, 🔴 — выходной)</i>"
    
    await query.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=build_calendar(now.year, now.month, "day_", "main_menu", user_slots),
    )


async def select_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    date_str = query.data.removeprefix("day_")
    
    clicked_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    if clicked_date < datetime.now().date():
        await safe_answer(query, "Этот день уже прошел!", show_alert=True)
        return
        
    if date_str in blocked_dates:
        await safe_answer(query, "Этот день закрыт для записи (выходной).", show_alert=True)
        return

    prune_expired_appointments(persist=True)
    day_slots = get_slots_for_date(date_str)
    booked_full = get_booked_slots()
    
    # Получаем только время занятых слотов для текущей даты
    booked_times = {slot.split("_")[1] for slot in booked_full if slot.startswith(date_str)}

    if not day_slots:
        await safe_answer(query, "На эту дату нет слотов!", show_alert=True)
        return

    await safe_answer(query)
    await query.message.reply_text(
        f"📅 Выбрана дата: <b>{date_str}</b>\nВыберите время:\n<i>(🔒 — время уже занято)</i>",
        parse_mode="HTML",
        reply_markup=build_time_keyboard(date_str, "time_", "signup", day_slots, booked_times),
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
        await safe_answer(query, "Этот слот уже успели занять! Пожалуйста, выберите другое время.", show_alert=True)
        return

    # Импорт TEACHER_ID внутри функции для предотвращения циклического импорта
    from ..config import TEACHER_ID
    if user_id == TEACHER_ID:
        context.user_data["admin_booking_slot"] = (slot, date_str, time_range)
        await safe_answer(query)
        await query.message.reply_text(
            f"✍️ Выбран слот: <b>{format_slot(slot, prefix='')}</b>\n\n"
            "Напишите в ответ <b>фамилию и имя</b> ученика для этой записи:",
            parse_mode="HTML",
        )
        return

    if user_id not in user_names:
        await query.message.reply_text("Пожалуйста, сначала отправьте команду /start и представьтесь.")
        await safe_answer(query)
        return

    appointments.setdefault(user_id, []).append(slot)
    appointment_times[slot] = get_slot_datetime(date_str, time_range)
    save_state()

    await safe_answer(query)
    await query.message.reply_text(f"✅ Вы успешно записались на <b>{format_slot(slot, prefix='')}</b>!", parse_mode="HTML")
    await main_menu(update, context)


async def my_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
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
    await safe_answer(query)
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
    await safe_answer(query)
    context.user_data["old_slot"] = query.data.removeprefix("change_select_")
    
    now = datetime.now()
    user_id = query.from_user.id
    user_slots = appointments.get(user_id, [])

    await query.message.reply_text(
        "Выберите новый день в календаре:",
        reply_markup=build_calendar(now.year, now.month, "change_day_", "main_menu", user_slots),
    )


async def change_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    date_str = query.data.removeprefix("change_day_")
    
    clicked_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    if clicked_date < datetime.now().date():
        await safe_answer(query, "Этот день уже прошел!", show_alert=True)
        return
        
    if date_str in blocked_dates:
        await safe_answer(query, "Этот день закрыт для записи.", show_alert=True)
        return

    await safe_answer(query)
    prune_expired_appointments(persist=True)

    old_slot = context.user_data.get("old_slot")
    booked_full = get_booked_slots()
    if old_slot:
        booked_full.discard(old_slot)

    day_slots = get_slots_for_date(date_str)
    booked_times = {slot.split("_")[1] for slot in booked_full if slot.startswith(date_str)}

    if not day_slots:
        await query.message.reply_text("На этот день нет свободного времени.")
        return

    await query.message.reply_text(
        f"📅 Выбрана дата: <b>{date_str}</b>\nВыберите новое время:\n<i>(🔒 — время уже занято)</i>",
        parse_mode="HTML",
        reply_markup=build_time_keyboard(date_str, "change_new_", "main_menu", day_slots, booked_times),
    )


async def change_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    prune_expired_appointments(persist=True)

    if user_id not in user_names:
        await query.message.reply_text("Пожалуйста, сначала отправьте команду /start.")
        await safe_answer(query)
        return

    raw_payload = query.data.removeprefix("change_new_")
    date_str, time_range = raw_payload.split("#", 1)
    new_slot = f"{date_str}_{time_range}"
    old_slot = context.user_data.get("old_slot")
    user_slots = appointments.get(user_id, [])

    if not old_slot or old_slot not in user_slots:
        await safe_answer(query)
        await query.message.reply_text("Ошибка: старая запись не найдена.")
        return

    booked = get_booked_slots()
    if old_slot:
        booked.discard(old_slot)

    if new_slot in booked:
        await safe_answer(query, "Этот слот уже занят. Выберите другое время.", show_alert=True)
        return

    user_slots.remove(old_slot)
    user_slots.append(new_slot)
    appointment_times.pop(old_slot, None)
    appointment_times[new_slot] = get_slot_datetime(date_str, time_range)
    save_state()

    await safe_answer(query)
    await query.message.reply_text(
        f"✅ Запись перенесена на <b>{format_slot(new_slot, prefix='')}</b>!\n\n📌 <b>Ваши текущие записи:</b>\n" + format_slot_list(user_slots),
        parse_mode="HTML",
    )
    await main_menu(update, context)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer(query)
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
        await safe_answer(query)
        return

    slot_time = appointment_times.get(slot)
    user_slots = appointments.get(user_id, [])
    await safe_answer(query)

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