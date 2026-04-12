from telegram import Update
from telegram.ext import ContextTypes

from ..config import TEACHER_ID
from ..helpers import format_slot, format_user_label
from ..state import appointment_times, appointments, prune_expired_appointments, save_state


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

    text = "📜 Все записи:\n"
    for user_id, slots in appointments.items():
        text += f"\n{format_user_label(user_id)}:\n"
        text += "\n".join(format_slot(slot, prefix="  - ") for slot in slots)

    await query.message.reply_text(text, parse_mode="HTML")


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != TEACHER_ID:
        await query.answer("❌ Нет доступа!", show_alert=True)
        return

    appointments.clear()
    appointment_times.clear()
    save_state()
    await query.answer()
    await query.message.reply_text("🔄 Все записи аннулированы!")
