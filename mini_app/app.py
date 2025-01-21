# quiz_project/mini_app/app.py

from flask import Flask, render_template, request, jsonify, send_from_directory, url_for
from flask_cors import CORS
import logging
import os



# Создаем экземпляр Flask
app = Flask(__name__, static_url_path='/static')
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


@app.route("/home.html")
def home():
    return render_template("home.html")


@app.route("/profile.html")
def profile():
    user = {"telegram_id": 975113235}  # Заглушка, замените на реальную логику получения пользователя
    return render_template("profile.html", user=user)


@app.route("/achievements.html")
def achievements():
    return render_template("achievements.html")


@app.route("/statistics.html")
def statistics():
    return render_template("statistics.html")


@app.route("/settings.html")
def settings():
    return render_template("settings.html")


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


@app.route("/profile/<int:telegram_id>/")
def user_profile(telegram_id):
    # Здесь добавить получение данных пользователя из базы данных
    user = {"telegram_id": telegram_id}  # Заглушка
    return render_template("profile.html", user=user)


@app.route("/section/<string:section_name>/")
def load_section(section_name):
    telegram_id = request.args.get('telegram_id')
    if not telegram_id:
        return "Telegram ID не указан", 400
    
    try:
        # Здесь добавить получение данных пользователя из базы данных
        user = {"telegram_id": telegram_id}  # Заглушка
        return render_template(f"sections/{section_name}.html", user=user)
    except Exception as e:
        app.logger.error(f"Ошибка: {str(e)}")
        return str(e), 500


@app.route("/profile/<int:telegram_id>/update/", methods=["POST"])
def update_profile(telegram_id):
    try:
        if 'avatar' in request.files:
            file = request.files['avatar']
            filename = f'user_{telegram_id}_{file.filename}'
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Здесь добавить обновление пути к аватару в базе данных
            
            return jsonify({
                'status': 'success',
                'message': 'Профиль успешно обновлен',
                'avatar_url': f'/uploads/{filename}'
            })
    except Exception as e:
        app.logger.error(f"Ошибка при обновлении профиля: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400


# Настройка загрузки файлов
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)