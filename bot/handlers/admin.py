from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from ..config import TEACHER_ID
from ..helpers import format_slot, format_user_label, get_available_dates
from ..state import (
    appointment_times,
    appointments,
    blocked_dates,
    prune_expired_appointments,
    save_state,
    user_names,
)
from telegram.error import BadRequest


async def safe_answer(query, *args, **kwargs):
    """Безопасный ответ на callback query без падения по таймауту."""
    try:
        await query.answer(*args, **kwargs)
    except BadRequest:
        pass


async def view_appointments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    prune_expired_appointments(persist=True)

    if query.from_user.id != TEACHER_ID:
        await query.answer("❌ Нет доступа!", show_alert=True)
        return

    await query.answer()
    if not appointments:
        await query.message.reply_text("Записей пока нет.")
        return

    text = "📋 <b>Все записи:</b>\n"
    keyboard = []

    for user_id, slots in appointments.items():
        user_label = format_user_label(user_id)
        clean_name = user_names.get(user_id, f"ID {user_id}")
        text += f"\n{user_label}:\n"
        for slot in slots:
            formatted_slot = format_slot(slot)
            text += f" - {formatted_slot}\n"
            btn_text = f"❌ {clean_name}: {formatted_slot}"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"adm_cancel_{user_id}_{slot}")])

    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="main_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.reply_text(
        text + "\n<i>Нажмите на кнопку ниже, чтобы отменить запись:</i>",
        parse_mode="HTML",
        reply_markup=reply_markup,
    )


async def admin_cancel_appointment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != TEACHER_ID:
        await query.answer("❌ Нет доступа!", show_alert=True)
        return

    prefix = "adm_cancel_"
    raw_data = query.data[len(prefix):]
    user_id_str, slot = raw_data.split("_", 1)
    target_user_id = int(user_id_str)

    if target_user_id in appointments and slot in appointments[target_user_id]:
        appointments[target_user_id].remove(slot)
        if not appointments[target_user_id]:
            del appointments[target_user_id]

        if target_user_id in appointment_times and slot in appointment_times[target_user_id]:
            del appointment_times[target_user_id][slot]
            if not appointment_times[target_user_id]:
                del appointment_times[target_user_id]

        save_state()
        await query.answer("✅ Запись отменена!", show_alert=True)

        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=f"⚠️ Преподаватель отменил вашу запись на: <b>{format_slot(slot)}</b>",
                parse_mode="HTML",
            )
        except Exception:
            pass
    else:
        await query.answer("Запись уже не найдена.", show_alert=True)

    await view_appointments(update, context)


async def manage_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает календарь дат для их закрытия/открытия админом."""
    query = update.callback_query
    if query.from_user.id != TEACHER_ID:
        await query.answer("❌ Нет доступа!", show_alert=True)
        return

    await query.answer()
    dates = get_available_dates()
    keyboard = []
    row = []

    for date_key, label in dates:
        # Если дата заблокирована, ставим значок замка/крестика
        status = "🔴" if date_key in blocked_dates else "🟢"
        btn_text = f"{status} {label}"
        row.append(InlineKeyboardButton(btn_text, callback_data=f"adm_toggle_{date_key}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("⬅️ В главное меню", callback_data="main_menu")])

    await query.message.reply_text(
        "🔒 <b>Управление рабочими днями:</b>\n\n"
        "🟢 — День открыт для записи\n"
        "🔴 — День закрыт (выходной)\n\n"
        "<i>Нажмите на день, чтобы изменить его статус:</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def toggle_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переключает статус даты (закрыт / открыт)."""
    query = update.callback_query
    if query.from_user.id != TEACHER_ID:
        await query.answer("❌ Нет доступа!", show_alert=True)
        return

    date_key = query.data.removeprefix("adm_toggle_")

    if date_key in blocked_dates:
        blocked_dates.remove(date_key)
        await query.answer(f"День {date_key} снова открыт для записи!")
    else:
        blocked_dates.add(date_key)
        await query.answer(f"День {date_key} закрыт для записи!")

    save_state()
    # Обновляем отображение списка дат
    await manage_days(update, context)


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != TEACHER_ID:
        await query.answer("❌ Нет доступа!", show_alert=True)
        return

    appointments.clear()
    appointment_times.clear()
    save_state()
    await safe_answer(query)
    await safe_answer(query, "🔄 Все записи аннулированы!", show_alert=True)