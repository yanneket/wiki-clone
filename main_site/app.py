from flask import Flask, render_template, request, jsonify
import logging
import requests
from datetime import datetime, timedelta
from threading import Lock
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__)))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, 'templates'),
    static_folder=os.path.join(BASE_DIR, 'static')
)

# Хранилище сбросов
active_resets = {}
reset_lock = Lock()
RESET_EXPIRE = timedelta(minutes=5)

BOT_TOKEN = '7953140297:AAGwWVx3zwmo-9MbQ-UUU1764nljCxuncQU'
# Настройка логов
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

@app.route('/')
def home():
    ref = request.args.get('ref', '')
    if ref:
        logger.info(f"Посещение от пользователя с ID: {ref}")
    return render_template('base.html')  # Ваш HTML-файл

@app.route('/log_query', methods=['POST'])
def log_query():
    data = request.json
    logger.info(f"Received data: {data}")  # Добавьте эту строку
    ref_id = data.get('ref')
    query = data.get('query')
    
    if not ref_id or not query:
        logger.error("Missing ref or query")  # Логируем ошибки
        return jsonify({'status': 'error'}), 400
    
    telegram_msg = f"🔍 Новый поиск по вашей ссылке!\nЗапрос: {query}\nID: {ref_id}"
    
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={'chat_id': ref_id, 'text': telegram_msg},
            timeout=5
        )
        logger.info(f"Telegram API response: {response.status_code} {response.text}")
    except Exception as e:
        logger.error(f"Telegram API error: {str(e)}")
    
    return jsonify({'status': 'ok'})


@app.route('/check_reset')
def check_reset():
    ref = request.args.get("ref")
    if not ref:
        return jsonify({'reset': False})

    with reset_lock:
        if ref in active_resets:
            del active_resets[ref]  # удаляем флаг сразу после срабатывания
            return jsonify({'reset': True})

    return jsonify({'reset': False})


@app.route('/trigger_reset')
def trigger_reset():
    ref = request.args.get("ref")
    if not ref:
        return "Missing ref", 400

    with reset_lock:
        active_resets[ref] = True  # ставим флаг сброса
    return "Reset triggered", 200



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)