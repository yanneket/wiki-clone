const BOT_FUNCTIONS = {
    // Копия функций из Telegram-бота
    generateLink: async (ref) => {
        try {
            const link = `https://wikpedia.ru?ref=${ref}`;
            navigator.clipboard.writeText(link);
            alert(`🔗 Ваша ссылка:\n${link}`);
        } catch (e) {
            alert("⚠️ Ошибка генерации ссылки");
        }
    },

    triggerReset: async (ref) => {
        try {
            // Проверяем состояние как в боте
            const checkRes = await fetch(`/check_reset_key?ref=${ref}`);
            const checkData = await checkRes.json();
            
            if (!checkData.exists) {
                alert("❌ Нечего удалять");
                return;
            }

            const res = await fetch(`/trigger_reset?ref=${ref}`);
            alert(res.ok ? "✅ Момент..." : "⚠️ Не удалось вызвать сброс");
        } catch (e) {
            alert("⚠️ Сервер недоступен");
        }
    },

    handleCodeWithCalc: (ref, callback) => {
        // Показываем калькулятор для ввода кода
        document.getElementById('calculator-mode').style.display = 'block';
        document.getElementById('bot-mode').style.display = 'none';
        
        // Настройка калькулятора
        setupCodeCalculator(ref, callback);
    }
};

// Калькулятор для ввода кода
function setupCodeCalculator(ref, callback) {
    let firstNumber = null;
    let operation = null;
    const screen = document.querySelector('#calculator-mode .screen');
    screen.textContent = '0';

    // Навешиваем новые обработчики прямо на живые кнопки
    document.querySelectorAll('#calculator-mode .calc-btn').forEach(btn => {
        const newBtn = btn.cloneNode(true); // копируем кнопку
        btn.replaceWith(newBtn); // заменяем в DOM

        newBtn.addEventListener('click', function () {
            const value = this.textContent;

            // Нажата цифра
            if (/\d/.test(value)) {
                screen.textContent = screen.textContent === '0' ? value : screen.textContent + value;
                return;
            }

            // Нажат знак умножения
            if (value === '×') {
                firstNumber = screen.textContent;
                operation = '×';
                screen.textContent = '0';
                return;
            }

            // Нажато "="
            if (value === '=' && operation === '×' && firstNumber) {
                const code = firstNumber;

                if (/^\d{4}$/.test(code)) {
                    callback(ref, code);
                } else {
                    alert("Код должен быть 4-значным числом");
                }

                // Возвращаемся к режиму бота
                document.getElementById('calculator-mode').style.display = 'none';
                document.getElementById('bot-mode').style.display = 'block';
            }
        });
    });
}


// Инициализация PWA
document.addEventListener('DOMContentLoaded', () => {
    // Проверяем авторизацию
    let storedRef = localStorage.getItem('user_ref');
    if (!storedRef) {
        const userRef = prompt("Введите ваш ID (число, выданное ботом):");
        if (userRef && /^\d+$/.test(userRef)) {
            localStorage.setItem('user_ref', userRef);
            storedRef = userRef;
        } else {
            alert("❌ Некорректный ID. Обновите страницу.");
            return;
        }
    }

    // Основное меню как в боте
    document.getElementById('copy-link').onclick = 
        () => BOT_FUNCTIONS.generateLink(storedRef);
    
    document.getElementById('reset-btn').onclick = 
        () => BOT_FUNCTIONS.triggerReset(storedRef);
    
    // Специальная обработка ввода кода через калькулятор
    document.getElementById('submit-code').onclick = () => {
        BOT_FUNCTIONS.handleCodeWithCalc(storedRef, async (ref, code) => {
            try {
                const res = await fetch(`https://wikicounter.ru/update_code`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        code: code,
                        new_url: `${BASE_SITE_URL}?ref=${ref}`
                    })
                });
                
                const data = await res.json();
                alert(data.status === "success" 
                    ? "✅ Код найден, устанавливаем связь..." 
                    : "❌ Код не найден");
            } catch (e) {
                alert("⚠️ Ошибка соединения");
            }
        });
    };
});