import calendar
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from telegram.error import BadRequest

from ..config import TEACHER_ID
from ..helpers import format_slot, get_available_dates
from ..state import (
    appointment_times,
    appointments,
    blocked_dates,
    prune_expired_appointments,
    save_state,
    user_names,
)


async def safe_answer(query, *args, **kwargs):
    try:
        await query.answer(*args, **kwargs)
    except BadRequest:
        pass


def get_all_booked_dates():
    """Собирает все даты, на которые есть хотя бы одна запись."""
    booked = set()
    for slots in appointments.values():
        for slot in slots:
            date_str = slot.split("_")[0]
            booked.add(date_str)
    return booked


def build_admin_calendar(year: int, month: int) -> InlineKeyboardMarkup:
    keyboard = []
    month_names = {1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель", 5: "Май", 6: "Июнь",
                   7: "Июль", 8: "Август", 9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"}

    keyboard.append([InlineKeyboardButton(f"📅 {month_names[month]} {year} (Все записи)", callback_data="ignore")])
    
    week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    keyboard.append([InlineKeyboardButton(day, callback_data="ignore") for day in week_days])

    cal = calendar.monthcalendar(year, month)
    booked_dates = get_all_booked_dates()

    for week in cal:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data="ignore"))
            else:
                date_str = f"{year}-{month:02d}-{day:02d}"
                
                # Синхронизированная логика отображения
                if date_str in blocked_dates:
                    btn_text = "🔴"
                elif date_str in booked_dates:
                    btn_text = f"{day} 🟢"
                else:
                    btn_text = str(day)

                row.append(InlineKeyboardButton(btn_text, callback_data=f"adm_day_{date_str}"))
        keyboard.append(row)

    prev_m = month - 1 if month > 1 else 12
    prev_y = year if month > 1 else year - 1
    next_m = month + 1 if month < 12 else 1
    next_y = year if month < 12 else year + 1

    keyboard.append([
        InlineKeyboardButton("⬅️", callback_data=f"adm_cal_nav_{prev_y}_{prev_m}"),
        InlineKeyboardButton("В меню", callback_data="main_menu"),
        InlineKeyboardButton("➡️", callback_data=f"adm_cal_nav_{next_y}_{next_m}")
    ])

    return InlineKeyboardMarkup(keyboard)


async def view_appointments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Открывает календарь со всеми записями."""
    query = update.callback_query
    prune_expired_appointments(persist=True)

    if query.from_user.id != TEACHER_ID:
        await safe_answer(query, "❌ Нет доступа!", show_alert=True)
        return

    now = datetime.now()
    await safe_answer(query)
    
    # Пытаемся изменить текущее сообщение...
    text = "📅 <b>Календарь записей:</b>\n<i>(🟢 — есть ученики, 🔴 — выходной)</i>\nВыберите дату:"
    try:
        await query.message.edit_text(text, parse_mode="HTML", reply_markup=build_admin_calendar(now.year, now.month))
    except Exception:
        await query.message.reply_text(text, parse_mode="HTML", reply_markup=build_admin_calendar(now.year, now.month))


async def admin_calendar_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Перелистывание месяцев в админском календаре."""
    query = update.callback_query
    if query.from_user.id != TEACHER_ID:
        await safe_answer(query, "❌ Нет доступа!", show_alert=True)
        return

    _, _, _, year_str, month_str = query.data.split("_")
    year, month = int(year_str), int(month_str)

    await safe_answer(query)
    try:
        await query.message.edit_reply_markup(reply_markup=build_admin_calendar(year, month))
    except BadRequest:
        pass


async def admin_view_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список записей на конкретный выбранный день."""
    query = update.callback_query
    if query.from_user.id != TEACHER_ID:
        await safe_answer(query, "❌ Нет доступа!", show_alert=True)
        return

    date_str = query.data.removeprefix("adm_day_")
    
    day_bookings = []
    for user_id, slots in appointments.items():
        for slot in slots:
            if slot.startswith(date_str):
                time_range = slot.split("_")[1]
                clean_name = user_names.get(user_id, f"ID {user_id}")
                day_bookings.append({
                    "user_id": user_id,
                    "slot": slot,
                    "time": time_range,
                    "name": clean_name
                })

    await safe_answer(query)
    now_dt = datetime.strptime(date_str, "%Y-%m-%d")
    
    if not day_bookings:
        keyboard = [[InlineKeyboardButton("⬅️ К календарю", callback_data=f"adm_cal_nav_{now_dt.year}_{now_dt.month}")]]
        await query.message.edit_text(
            f"На <b>{date_str}</b> записей нет.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # Сортируем записи по времени от утра к вечеру
    day_bookings.sort(key=lambda x: x["time"])

    text = f"📋 <b>Записи на {date_str}:</b>\n\n"
    keyboard = []

    for b in day_bookings:
        text += f"⏰ {b['time']} — {b['name']}\n"
        btn_text = f"❌ {b['time']} ({b['name']})"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"adm_cancel_{b['user_id']}_{b['slot']}")])

    keyboard.append([InlineKeyboardButton("⬅️ К календарю", callback_data=f"adm_cal_nav_{now_dt.year}_{now_dt.month}")])

    await query.message.edit_text(
        text + "\n<i>Нажмите на кнопку ниже, чтобы отменить запись:</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def admin_cancel_appointment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаляет запись и возвращает админа к списку этого же дня."""
    query = update.callback_query
    if query.from_user.id != TEACHER_ID:
        await safe_answer(query, "❌ Нет доступа!", show_alert=True)
        return

    prefix = "adm_cancel_"
    raw_data = query.data[len(prefix):]
    user_id_str, slot = raw_data.split("_", 1)
    target_user_id = int(user_id_str)
    date_str = slot.split("_")[0]

    if target_user_id in appointments and slot in appointments[target_user_id]:
        appointments[target_user_id].remove(slot)
        if not appointments[target_user_id]:
            del appointments[target_user_id]

        if target_user_id in appointment_times and slot in appointment_times[target_user_id]:
            del appointment_times[target_user_id][slot]
            if not appointment_times[target_user_id]:
                del appointment_times[target_user_id]

        save_state()
        await safe_answer(query, "✅ Запись отменена!", show_alert=True)

        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=f"⚠️ Преподаватель отменил вашу запись на: <b>{format_slot(slot)}</b>",
                parse_mode="HTML",
            )
        except Exception:
            pass
    else:
        await safe_answer(query, "Запись уже не найдена.", show_alert=True)

    # Имитируем нажатие на этот же день, чтобы обновить список
    query.data = f"adm_day_{date_str}"
    await admin_view_day(update, context)


async def manage_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != TEACHER_ID:
        await safe_answer(query, "❌ Нет доступа!", show_alert=True)
        return

    await safe_answer(query)
    dates = get_available_dates()
    keyboard = []
    row = []

    for date_key, label in dates:
        status = "🔴" if date_key in blocked_dates else "🟢"
        btn_text = f"{status} {label}"
        row.append(InlineKeyboardButton(btn_text, callback_data=f"adm_toggle_{date_key}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("⬅️ В главное меню", callback_data="main_menu")])

    try:
        await query.message.edit_text(
            "🔒 <b>Управление рабочими днями:</b>\n\n"
            "🟢 — День открыт для записи\n"
            "🔴 — День закрыт (выходной)\n\n"
            "<i>Нажмите на день, чтобы изменить его статус:</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    except Exception:
        pass


async def toggle_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != TEACHER_ID:
        await safe_answer(query, "❌ Нет доступа!", show_alert=True)
        return

    date_key = query.data.removeprefix("adm_toggle_")

    if date_key in blocked_dates:
        blocked_dates.remove(date_key)
        await safe_answer(query, f"День {date_key} снова открыт для записи!")
    else:
        blocked_dates.add(date_key)
        await safe_answer(query, f"День {date_key} закрыт для записи!")

    save_state()
    await manage_days(update, context)


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != TEACHER_ID:
        await safe_answer(query, "❌ Нет доступа!", show_alert=True)
        return

    appointments.clear()
    appointment_times.clear()
    save_state()
    await safe_answer(query)
    await query.message.edit_text("🔄 Все записи аннулированы!")