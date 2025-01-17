# quiz_project/mini_app/app.py

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import logging



# Создаем экземпляр Flask
app = Flask(__name__)
CORS(app)  # Включаем поддержку CORS для взаимодействия с клиентом


# Настраиваем логирование
logging.basicConfig(level=logging.DEBUG)



@app.route("/")
def index():
    """
    Главная страница мини-приложения.
    Возвращает HTML-страницу с кнопкой и местом для отображения данных.
    """
    return render_template("index.html")


@app.route("/api/test-api/", methods=["GET"])
def test_api():
    """
    Пример серверного API.
    Возвращает JSON с сообщением.
    """
    app.logger.info("Запрос к API /api/test-api/")
    return jsonify({"message": "Сообщение от API"})


@app.route("/api/button-click", methods=["POST"])
def button_click():
    """
    Обработка нажатия на кнопку.
    Получает данные из POST-запроса и возвращает подтверждение.
    """
    data = request.json
    app.logger.info(f"Получен запрос: {data}")
    return jsonify({"status": "success", "message": "Данные обработаны"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)