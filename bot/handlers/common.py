from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from ..config import TEACHER_ID
from ..state import prune_expired_appointments, save_state, user_names


def build_main_menu_markup(user_id):
    keyboard = [
        [InlineKeyboardButton("📅 Записаться", callback_data="signup")],
        [InlineKeyboardButton("🔍 Мои записи", callback_data="mybookings")],
        [InlineKeyboardButton("⏳ Изменить запись", callback_data="change")],
        [InlineKeyboardButton("❌ Отменить запись", callback_data="cancel")],
    ]

    if user_id == TEACHER_ID:
        keyboard.append([InlineKeyboardButton("📜 Все записи", callback_data="view")])
        keyboard.append([InlineKeyboardButton("🔄 Сброс записей", callback_data="reset")])

    return InlineKeyboardMarkup(keyboard)


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prune_expired_appointments(persist=True)

    if update.callback_query and update.callback_query.data == "main_menu":
        await update.callback_query.answer()

    await update.effective_chat.send_message(
        "Выбери действие:",
        reply_markup=build_main_menu_markup(update.effective_user.id),
    )


async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in user_names:
        context.user_data["awaiting_name"] = True
        await update.message.reply_text("Как тебя зовут? Напиши свое имя:")
        return

    context.user_data["awaiting_name"] = False
    await main_menu(update, context)


async def save_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_name"):
        return

    user_id = update.message.from_user.id
    user_name = update.message.text.strip()

    if not user_name:
        await update.message.reply_text("Имя не должно быть пустым. Напиши, как тебя зовут:")
        return

    if len(user_name) > 64:
        await update.message.reply_text("Имя слишком длинное. Напиши короткий вариант, до 64 символов.")
        return

    user_names[user_id] = user_name
    context.user_data["awaiting_name"] = False
    save_state()
    await main_menu(update, context)
