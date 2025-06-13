from flask import Flask, render_template, request, jsonify, make_response
import logging
import requests
from datetime import timedelta, datetime
import os
import redis
import json

# === Настройки ===
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__)))
BOT_TOKEN = '7953140297:AAGwWVx3zwmo-9MbQ-UUU1764nljCxuncQU'
RESET_EXPIRE_SECONDS = 30  # для Redis TTL

# === Redis клиент ===
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

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

# === Вспомогательные функции для работы с Redis ===

def set_reset(ref_id, expire_seconds=None, manual=False):
    data = {"manual": manual}
    key = f"reset:{ref_id}"
    redis_client.set(key, json.dumps(data))
    if expire_seconds is not None:
        redis_client.expire(key, expire_seconds)

def get_reset(ref_id):
    key = f"reset:{ref_id}"
    raw = redis_client.get(key)
    ttl = redis_client.ttl(key)
    logger.info(f"[GET_RESET] Получен ключ {key}: {raw}, TTL={ttl}")

    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning(f"[GET_RESET] Ошибка JSON декодирования ключа {key}")
        return None


def try_lock_reset(ref_id):
    key = f"lock:reset:{ref_id}"
    return redis_client.set(key, '1', nx=True, ex=2)


def delete_reset(ref_id):
    key = f"reset:{ref_id}"
    redis_client.delete(key)

# === Маршруты ===

@app.route('/')
def home():
    ref = request.args.get('ref', '')
    if ref:
        logger.info(f"[HOME] Посещение с ID: {ref}")
    response = make_response(render_template('base.html'))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


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

    # Устанавливаем сброс в Redis с TTL
    set_reset(ref_id, expire_seconds=RESET_EXPIRE_SECONDS, manual=False)
    logger.info(f"[LOG_QUERY] Установлен таймер сброса для ID: {ref_id}")

    return jsonify({'status': 'ok'})


@app.route('/check_reset')
def check_reset():
    logger.warning("[DEBUG] request.args: %s", dict(request.args))
    ref = request.args.get("ref")
    if not ref:
        logger.info("[CHECK_RESET] Нет параметра ref")
        return jsonify({'reset': False})

    logger.info(f"[CHECK_RESET] Проверка сброса для ID: {ref}")
    reset_data = get_reset(ref)

    if reset_data:
        manual = reset_data.get("manual", False)

        if manual:
            if try_lock_reset(ref):
                logger.info(f"[CHECK_RESET] Сработал ручной сброс для ID: {ref}")
                delete_reset(ref)
                try:
                    message = f"🔄 Сработал сброс для ID: {ref}\nТип: ручной"
                    requests.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                        json={"chat_id": ref, "text": message}
                    )
                except Exception as e:
                    logger.error(f"[CHECK_RESET] Ошибка отправки в Telegram: {e}")
            else:
                logger.info(f"[CHECK_RESET] Повторный ручной сброс проигнорирован для ID: {ref}")
            return jsonify({'reset': True})

        else:
            logger.info(f"[CHECK_RESET] Сброс не сработал, ждем истечения TTL для ID: {ref}")
            return jsonify({'reset': False})
    else:
        # автоматический сброс (по TTL)
        if try_lock_reset(ref):
            logger.info(f"[CHECK_RESET] Автоматический сброс сработал для ID: {ref}")
            try:
                message = f"🔄 Сработал сброс для ID: {ref}\nТип: автоматический (истечение таймера)"
                requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={"chat_id": ref, "text": message}
                )
            except Exception as e:
                logger.error(f"[CHECK_RESET] Ошибка отправки в Telegram: {e}")
        else:
            logger.info(f"[CHECK_RESET] Повторный авто-сброс проигнорирован для ID: {ref}")

        return jsonify({'reset': True})



@app.route('/trigger_reset')
def trigger_reset():
    ref = request.args.get("ref")
    if not ref:
        logger.warning("[TRIGGER_RESET] Отсутствует параметр ref")
        return "Missing ref", 400

    # Устанавливаем в Redis ручной сброс без TTL (вечный)
    set_reset(ref, expire_seconds=120, manual=True)
    logger.info(f"[TRIGGER_RESET] Установлен ручной сброс для ID: {ref}")
    return "Reset triggered", 200


@app.route('/check_reset_key')
def check_reset_key():
    ref = request.args.get("ref")
    if not ref:
        return jsonify({'exists': False, 'error': 'No ref provided'}), 400
    key = f"reset:{ref}"
    exists = redis_client.exists(key)
    return jsonify({'exists': bool(exists)})


@app.route('/calculator')
def calculator():
    ref = request.args.get('ref')
    if not ref:
        return "❌ Missing ref", 400
    return render_template('calculator.html', ref=ref)
