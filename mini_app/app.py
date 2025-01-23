# quiz_project/mini_app/app.py

from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import logging
import os
from fastapi.middleware.cors import CORSMiddleware

# Создаем экземпляр Flask
app = FastAPI(debug=True)

# Настраиваем логирование
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Настройка загрузки файлов
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Включаем CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Проверяем наличие директорий и файлов
static_dir = os.path.join(os.path.dirname(__file__), "static")
logger.info(f"Static directory: {static_dir}")
logger.info(f"Static directory exists: {os.path.exists(static_dir)}")
if os.path.exists(static_dir):
    logger.info(f"Static directory contents: {os.listdir(static_dir)}")

# Подключаем статические файлы
app.mount("/static", StaticFiles(directory="static"), name="static")

# Подключаем шаблоны
templates = Jinja2Templates(directory="templates")


# Читаем CSS файлы
def read_css():
    css_content = ""
    css_dir = os.path.join(os.path.dirname(__file__), "static", "css")
    for file in ["main.css", "gallery.css", "navigation.css"]:
        with open(os.path.join(css_dir, file)) as f:
            css_content += f.read() + "\n"
    return css_content


# Сохраняем CSS один раз при запуске
CSS_CONTENT = read_css()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """
    Главная страница мини-приложения.
    Возвращает HTML-страницу с кнопкой и местом для отображения данных.
    """
    try:
        logger.info("Rendering index page")
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "css_content": CSS_CONTENT
            }
        )
    except Exception as e:
        logger.error(f"Error rendering index page: {str(e)}")
        return HTMLResponse(content=str(e), status_code=500)


@app.get("/profile", response_class=HTMLResponse)
async def profile(request: Request):
    return templates.TemplateResponse("profile.html", {"request": request, "css_content": CSS_CONTENT})


@app.get("/achievements", response_class=HTMLResponse)
async def achievements(request: Request):
    return templates.TemplateResponse("achievements.html", {"request": request, "css_content": CSS_CONTENT})


@app.get("/statistics", response_class=HTMLResponse)
async def statistics(request: Request):
    return templates.TemplateResponse("statistics.html", {"request": request, "css_content": CSS_CONTENT})


@app.get("/settings", response_class=HTMLResponse)
async def settings(request: Request):
    return templates.TemplateResponse("settings.html", {"request": request, "css_content": CSS_CONTENT})


@app.get("/api/test-api/")
async def test_api():
    """
    Пример серверного API.
    Возвращает JSON с сообщением.
    """
    app.logger.info("Запрос к API /api/test-api/")
    return {"message": "Сообщение от API"}


@app.post("/api/button-click")
async def button_click(data: dict):
    """
    Обработка нажатия на кнопку.
    Получает данные из POST-запроса и возвращает подтверждение.
    """
    app.logger.info(f"Получен запрос: {data}")
    return {"status": "success", "message": "Данные обработаны"}


@app.get("/profile/{telegram_id}/", response_class=HTMLResponse)
async def user_profile(request: Request, telegram_id: int):
    # Здесь добавить получение данных пользователя из базы данных
    user = {"telegram_id": telegram_id}  # Заглушка
    return templates.TemplateResponse("profile.html", {"request": request, "user": user, "css_content": CSS_CONTENT})


@app.get("/section/{section_name}/", response_class=HTMLResponse)
async def load_section(request: Request, section_name: str, telegram_id: int):
    try:
        # Здесь добавить получение данных пользователя из базы данных
        user = {"telegram_id": telegram_id}  # Заглушка
        return templates.TemplateResponse(f"sections/{section_name}.html",
                                          {"request": request, "user": user, "css_content": CSS_CONTENT})
    except Exception as e:
        app.logger.error(f"Ошибка: {str(e)}")
        return JSONResponse(content={"message": str(e)}, status_code=500)


@app.post("/profile/{telegram_id}/update/")
async def update_profile(telegram_id: int, avatar: UploadFile = File(...)):
    try:
        filename = f'user_{telegram_id}_{avatar.filename}'
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        with open(filepath, 'wb') as file:
            contents = await avatar.read()
            file.write(contents)

        # Здесь добавить обновление пути к аватару в базе данных

        return {"status": "success", "message": "Профиль успешно обновлен", "avatar_url": f'/uploads/{filename}'}
    except Exception as e:
        app.logger.error(f"Ошибка при обновлении профиля: {str(e)}")
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=400)


if __name__ == "__main__":
    import uvicorn

    logger.info("Starting server on port 8080")
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="debug")