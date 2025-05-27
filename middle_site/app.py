from flask import Flask, render_template, request, jsonify
import random
from datetime import datetime, timedelta
from threading import Lock
import logging
import time
import threading
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__)))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, 'templates'),
    static_folder=os.path.join(BASE_DIR, 'static')
)

# Хранилище кодов и ссылок
code_storage = {}
storage_lock = Lock()
CODE_EXPIRE = timedelta(minutes=10)

# Настройка логов
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

@app.route('/')
def index():
    # Генерируем 4-значный код
    code = str(random.randint(1000, 9999))
    
    # Сохраняем код с временной меткой
    with storage_lock:
        code_storage[code] = {
            'created': datetime.now(),
            'target_url': "https://ru.wikipedia.org/wiki/",  # Изначально ведет на Википедию
            'used': False
        }
    
    logger.info(f"Generated code: {code}")
    return render_template('base.html', code=code)

@app.route('/update_code', methods=['POST'])
def update_code():
    data = request.json
    print("\n=== ПОЛУЧЕН ЗАПРОС НА ОБНОВЛЕНИЕ КОДА ===")
    print(f"Входные данные: {data}")
    
    code = data.get('code')
    new_url = data.get('new_url')
    
    if not code or not new_url:
        print("Ошибка: отсутствует код или URL")
        return jsonify({'status': 'error', 'message': 'Missing parameters'}), 400
    
    with storage_lock:
        print(f"Текущее хранилище кодов: {code_storage}")
        if code in code_storage:
            print(f"Найден код {code}. Старый URL: {code_storage[code]['target_url']}")
            code_storage[code]['target_url'] = new_url
            code_storage[code]['used'] = True
            print(f"Обновленный код {code}: {code_storage[code]}")
            return jsonify({'status': 'success'})
    
    print(f"Код {code} не найден в хранилище")
    return jsonify({'status': 'error', 'message': 'Code not found'}), 404

@app.route('/get_target_url')
def get_target_url():
    code = request.args.get('code')
    print("\n=== ПОЛУЧЕН ЗАПРОС НА ПОЛУЧЕНИЕ URL ===")
    print(f"Запрошенный код: {code}")
    
    if not code:
        print("Ошибка: код не указан")
        return jsonify({'error': 'Code missing'}), 400
    
    with storage_lock:
        print(f"Текущее хранилище: {code_storage}")
        if code in code_storage:
            print(f"Возвращаем URL для кода {code}: {code_storage[code]['target_url']}")
            return jsonify({
                'url': code_storage[code]['target_url'],
                'is_updated': code_storage[code]['used']
            })
    
    print("Код не найден, возвращаем Википедию")
    return jsonify({'url': "https://ru.wikipedia.org/wiki/", 'is_updated': False})

def cleanup_expired_codes():
    """Очистка устаревших кодов"""
    while True:
        now = datetime.now()
        with storage_lock:
            expired = [code for code, data in code_storage.items() 
                      if (now - data['created']) > CODE_EXPIRE]
            for code in expired:
                del code_storage[code]
        time.sleep(60)

if __name__ == '__main__':
    # Запускаем очистку устаревших кодов в фоне
    threading.Thread(target=cleanup_expired_codes, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
