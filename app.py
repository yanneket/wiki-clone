from flask import Flask, request, Response
import requests
import re
from bs4 import BeautifulSoup
import os

app = Flask(__name__)
BASE_URL = "https://ru.m.wikipedia.org"

@app.route('/')
def wiki_proxy():
    search_query = request.args.get("search")
    page = search_query if search_query else "Ирбис"
    url = f"{BASE_URL}/wiki/{page}"

    try:
        r = requests.get(url)
        r.encoding = "utf-8"
    except Exception as e:
        return f"<h1>Ошибка загрузки страницы: {e}</h1>"

    soup = BeautifulSoup(r.text, "html.parser")
    content_div = soup.find("div", class_="mw-parser-output")

    # Удаляем ненужные элементы
    for script in soup.find_all("script"):
        script.decompose()
    for style in soup.find_all("style"):
        style.decompose()
    for form in soup.find_all("form"):
        form.decompose()

    # Кастомная форма в контейнере
    custom_form = BeautifulSoup("""
    <div class="search-container" onclick="event.stopPropagation()" style="position: relative; z-index: 10; background: white;">
        <form action="/" method="get" class="minerva-search-form">
            <div class="search-box">
                <input type="hidden" name="title" value="Служебная:Поиск"/>
                <input class="search skin-minerva-search-trigger" id="searchInput"
                       type="search" name="search" placeholder="Искать в Википедии" 
                       aria-label="Искать в Википедии"
                       autocapitalize="sentences" title="Искать в Википедии [f]" accesskey="f">
                <span class="search-box-icon-overlay">
                    <span class="minerva-icon minerva-icon--search"></span>
                </span>
            </div>
        </form>
    </div>
    """, "html.parser")

    script = soup.new_tag("script")
    script.string = """
document.addEventListener("DOMContentLoaded", function () {
    const searchInput = document.getElementById('searchInput');
    const footer = document.querySelector('footer');
    const body = document.body;
    const html = document.documentElement;

    if (!searchInput || !footer) return;

    searchInput.addEventListener("focus", function () {
        // Скрываем текст в футере
        const footerText = footer.querySelectorAll('*');
        footerText.forEach(element => {
            element.style.visibility = 'hidden';
        });

        // Меняем фон футера на белый
        footer.style.backgroundColor = 'white';
    });

    // Восстановление текста в футере и восстановление фона футера, когда пользователь кликает вне поля поиска
    document.addEventListener("click", function (event) {
        if (!searchInput.contains(event.target)) {
            const footerText = footer.querySelectorAll('*');
            footerText.forEach(element => {
                element.style.visibility = '';
            });
            footer.style.backgroundColor = '';  // Восстанавливаем фон футера
        }
    });
});
"""

    soup.body.append(script)

    if not content_div:
        return "<h1>Контент не найден на странице</h1>"

    # Вставляем форму после логотипа
    header_div = soup.find("div", class_="branding-box")
    if header_div:
        header_div.insert_after(custom_form)

    # Для результатов поиска — оставляем только краткое описание и инфоблоки
    if search_query:
        new_content = BeautifulSoup("", "html.parser")
        first_p = content_div.find("p")
        if first_p:
            new_content.append(first_p)
        for table in content_div.find_all("table", class_=re.compile("infobox")):
            new_content.append(table)
        hello = soup.new_tag("p")
        hello.string = "Привет!"
        new_content.append(hello)
        content_div.clear()
        content_div.append(new_content)

    # Правим ссылки и изображения
    html = str(soup)
    html = re.sub(r'href="(/[^"]+)"', f'href="{BASE_URL}\\1"', html)
    html = re.sub(r'src="(/[^"]+)"', f'src="{BASE_URL}\\1"', html)

    return Response(html, mimetype="text/html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
