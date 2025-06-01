from flask import Flask, render_template, request, jsonify
import logging
import requests
from datetime import timedelta, datetime
from threading import Lock
import os

# === Настройки ===
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__)))
BOT_TOKEN = '7953140297:AAGwWVx3zwmo-9MbQ-UUU1764nljCxuncQU'
RESET_EXPIRE = timedelta(seconds=30)

# === Flask-приложение ===
app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, 'templates'),
    static_folder=os.path.join(BASE_DIR, 'static')
)

# === Логирование ===
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# === Хранилище сбросов ===
active_resets = {}
reset_lock = Lock()

# === Маршруты ===

@app.route('/')
def home():
    ref = request.args.get('ref', '')
    if ref:
        logger.info(f"[HOME] Посещение с ID: {ref}")
    return render_template('base.html')


@app.route('/log_query', methods=['POST'])
def log_query():
    data = request.json
    logger.info(f"[LOG_QUERY] Получен запрос: {data}")

    ref_id = data.get('ref')
    query = data.get('query')

    if not ref_id or not query:
        logger.warning("[LOG_QUERY] Пропущены параметры ref или query")
        return jsonify({'status': 'error'}), 400

    telegram_msg = f"🔍 Новый поиск по вашей ссылке!\nЗапрос: {query}\nID: {ref_id}"

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={'chat_id': ref_id, 'text': telegram_msg},
            timeout=5
        )
        logger.info(f"[LOG_QUERY] Telegram API: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"[LOG_QUERY] Ошибка Telegram API: {e}")

    with reset_lock:
        active_resets[ref_id] = {
            "expire": datetime.utcnow() + RESET_EXPIRE,
            "manual": False
        }
        logger.info(f"[LOG_QUERY] Установлен таймер сброса для ID: {ref_id}")

    return jsonify({'status': 'ok'})


@app.route('/check_reset')
def check_reset():
    ref = request.args.get("ref")
    if not ref:
        logger.info("[CHECK_RESET] Нет параметра ref")
        return jsonify({'reset': False})

    with reset_lock:
        reset_data = active_resets.get(ref)
        if reset_data:
            expired = reset_data["expire"] and datetime.utcnow() >= reset_data["expire"]
            manual = reset_data["manual"]

            if expired or manual:
                logger.info(f"[CHECK_RESET] Сработал сброс для ID: {ref} (manual={manual}, expired={expired})")
                del active_resets[ref]
                return jsonify({'reset': True})

    logger.info(f"[CHECK_RESET] Нет сброса для ID: {ref}")
    logger.info(f"[DEBUG] Текущее состояние active_resets: {active_resets}")

    return jsonify({'reset': False})


@app.route('/trigger_reset')
def trigger_reset():
    ref = request.args.get("ref")
    if not ref:
        logger.warning("[TRIGGER_RESET] Отсутствует параметр ref")
        return "Missing ref", 400

    with reset_lock:
        if ref not in active_resets:
            active_resets[ref] = {"expire": None, "manual": True}
        else:
            active_resets[ref]["manual"] = True
        logger.info(f"[TRIGGER_RESET] Установлен ручной сброс для ID: {ref}")
    return "Reset triggered", 200


# === Запуск приложения ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"🚀 Запуск сервера на порту {port}")
    app.run(host='0.0.0.0', port=port)
