from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from .handlers.admin import admin_cancel_appointment, manage_days, reset, toggle_day, view_appointments
from .config import TOKEN
from .handlers.admin import admin_cancel_appointment, reset, view_appointments
from .handlers.common import ask_name, main_menu, save_name
from .handlers.user import (
    cancel,
    cancel_select,
    change,
    change_day,
    change_new,
    change_select,
    my_bookings,
    select_day,
    select_time,
    signup,
)
from .state import load_state


def build_application():
    if not TOKEN:
        raise RuntimeError("Укажи TELEGRAM_BOT_TOKEN в переменных окружения перед запуском бота.")

    load_state()
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", ask_name))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, save_name))

    app.add_handler(CallbackQueryHandler(main_menu, pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(signup, pattern="^signup$"))
    app.add_handler(CallbackQueryHandler(my_bookings, pattern="^mybookings$"))
    app.add_handler(CallbackQueryHandler(view_appointments, pattern="^view$"))
    app.add_handler(CallbackQueryHandler(admin_cancel_appointment, pattern="^adm_cancel_"))
    app.add_handler(CallbackQueryHandler(reset, pattern="^reset$"))

    app.add_handler(CallbackQueryHandler(select_day, pattern="^day_"))
    app.add_handler(CallbackQueryHandler(select_time, pattern="^time_"))
    app.add_handler(CallbackQueryHandler(change, pattern="^change$"))
    app.add_handler(CallbackQueryHandler(change_select, pattern="^change_select_"))
    app.add_handler(CallbackQueryHandler(change_day, pattern="^change_day_"))
    app.add_handler(CallbackQueryHandler(change_new, pattern="^change_new_"))
    app.add_handler(CallbackQueryHandler(cancel, pattern="^cancel$"))
    app.add_handler(CallbackQueryHandler(cancel_select, pattern="^cancel_select_"))

    app.add_handler(CallbackQueryHandler(manage_days, pattern="^manage_days$"))
    app.add_handler(CallbackQueryHandler(toggle_day, pattern="^adm_toggle_"))

    return app


def main():
    app = build_application()
    print("Бот запущен...")
    app.run_polling(drop_pending_updates=True)