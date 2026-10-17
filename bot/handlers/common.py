from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from ..config import TEACHER_ID
from ..helpers import format_slot, get_slot_datetime
from ..state import (
    appointment_times,
    appointments,
    prune_expired_appointments,
    save_state,
    user_names,
)


def build_main_menu_markup(user_id):
    keyboard = [
        [InlineKeyboardButton("📅 Записаться", callback_data="signup")],
        [InlineKeyboardButton("🔍 Мои записи", callback_data="mybookings")],
        [InlineKeyboardButton("⏳ Изменить запись", callback_data="change")],
        [InlineKeyboardButton("❌ Отменить мою запись", callback_data="cancel")],
    ]

    if user_id == TEACHER_ID:
        keyboard.append([InlineKeyboardButton("📋 Все записи", callback_data="view")])
        keyboard.append([InlineKeyboardButton("🔒 Закрыть/открыть день", callback_data="manage_days")])
        keyboard.append([InlineKeyboardButton("🔄 Сбросить все записи", callback_data="reset")])

    return InlineKeyboardMarkup(keyboard)


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prune_expired_appointments(persist=True)

    if update.callback_query and update.callback_query.data == "main_menu":
        try:
            await update.callback_query.answer()
        except Exception:
            pass

    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat:
        return

    await chat.send_message(
        "Выбери действие:",
        reply_markup=build_main_menu_markup(user.id),
    )


async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.effective_message

    if not user or not message:
        return

    user_id = user.id

    # Если пользователь уже называл свое имя — сразу открываем главное меню
    if user_id in user_names:
        await main_menu(update, context)
        return

    await message.reply_text(
        "👋 Напиши, пожалуйста, свою <b>фамилию</b>:",
        parse_mode="HTML",
    )


async def save_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.effective_message

    if not user or not message or not message.text:
        return

    user_id = user.id
    text = message.text.strip()

    # 1. Проверяем, вводит ли админ фамилию ученика для ручной записи
    if "admin_booking_slot" in context.user_data:
        slot, date_str, time_range = context.user_data.pop("admin_booking_slot")

        booked = {s for slots in appointments.values() for s in slots}
        if slot in booked:
            await message.reply_text("❌ Пока вы вводили фамилию, этот слот уже заняли.")
            await main_menu(update, context)
            return

        # Уникальный виртуальный ID для ученика
        virtual_user_id = -int(datetime.now().timestamp() * 1000)

        user_names[virtual_user_id] = text
        appointments.setdefault(virtual_user_id, []).append(slot)
        appointment_times[slot] = get_slot_datetime(date_str, time_range)
        save_state()

        await message.reply_text(
            f"✅ Ученик <b>{text}</b> успешно записан на <b>{format_slot(slot, prefix='')}</b>!",
            parse_mode="HTML",
        )
        await main_menu(update, context)
        return

    # 2. Обычное сохранение имени/фамилии пользователя при старте
    user_names[user_id] = text
    save_state()

    await message.reply_text(f"Приятно познакомиться, {text}!")
    await main_menu(update, context)