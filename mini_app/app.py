# quiz_project/mini_app/app.py

from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import logging
import os
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

# Создаём экземпляр FastAPI
app = FastAPI(debug=True)

# Настраиваем логирование
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Папка для загрузки пользовательских файлов (аватарок и т.п.)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Включаем CORS (разрешаем доступ с любых доменов)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Разрешить все домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)




@app.get("/static/css/{filename}")
async def serve_css(filename: str):
    return FileResponse(f"static/css/{filename}", headers={"Cache-Control": "no-store, no-cache, must-revalidate"})



# Путь к папке со статическими файлами
current_dir = os.path.dirname(__file__)
static_dir = os.path.join(current_dir, 'static')

# Проверяем существование папки со статикой
logger.info(f"Static directory: {static_dir}")
logger.info(f"Static directory exists: {os.path.exists(static_dir)}")

# Монтируем папку static как /static
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Подключаем папку с шаблонами (templates/)
templates_dir = os.path.join(current_dir, "templates")
templates = Jinja2Templates(directory=templates_dir)

# Обработка главной страницы
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    logger.info("Rendering index page")
    return templates.TemplateResponse("index.html", {"request": request})

# Обработка страницы профиля
@app.get("/profile", response_class=HTMLResponse)
async def profile(request: Request):
    logger.info("Rendering profile page")
    user = {
        "telegram_id": 123456789,
        "username": "JohnDoe",
        "avatar_url": "/static/images/default_avatar.png"
    }
    return templates.TemplateResponse("profile.html", {"request": request, "user": user})

# Обработка страницы достижений
@app.get("/achievements", response_class=HTMLResponse)
async def achievements(request: Request):
    logger.info("Rendering achievements page")
    achievements = [
        {"id": 1, "title": "Достижение 1", "description": "Описание достижения 1", "image_url": "https://picsum.photos/200/200?21"},
        {"id": 2, "title": "Достижение 2", "description": "Описание достижения 2", "image_url": "https://picsum.photos/200/200?22"},
        {"id": 3, "title": "Достижение 3", "description": "Описание достижения 3", "image_url": "https://picsum.photos/200/200?23"},
    ]
    return templates.TemplateResponse("achievements.html", {"request": request, "achievements": achievements})

# Обработка страницы статистики
@app.get("/statistics", response_class=HTMLResponse)
async def statistics(request: Request):
    logger.info("Rendering statistics page")
    return templates.TemplateResponse("statistics.html", {"request": request})

# Обработка страницы настроек
@app.get("/settings", response_class=HTMLResponse)
async def settings(request: Request):
    logger.info("Rendering settings page")
    user = {
        "telegram_id": 123456789,
        "username": "JohnDoe",
        "avatar_url": "/static/images/default_avatar.png"
    }
    return templates.TemplateResponse("settings.html", {"request": request, "user": user})

# Пример API
@app.get("/api/test-api/")
async def test_api():
    logger.info("Запрос к API /api/test-api/")
    return {"message": "Сообщение от API"}

# Пример POST-обработчика
@app.post("/api/button-click")
async def button_click(data: dict):
    logger.info(f"Получен запрос: {data}")
    return {"status": "success", "message": "Данные обработаны"}

# Пример динамического URL: /profile/123/
@app.get("/profile/{telegram_id}/", response_class=HTMLResponse)
async def user_profile(request: Request, telegram_id: int):
    user = {"telegram_id": telegram_id, "username": f"User{telegram_id}", "avatar_url": "/static/images/default_avatar.png"}
    logger.info(f"Rendering user profile for Telegram ID: {telegram_id}")
    return templates.TemplateResponse("profile.html", {"request": request, "user": user})

# Обработка загрузки аватарки
@app.post("/profile/{telegram_id}/update/", response_class=JSONResponse)
async def update_profile(telegram_id: int, avatar: UploadFile = File(...)):
    try:
        filename = f'user_{telegram_id}_{avatar.filename}'
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        with open(filepath, 'wb') as file:
            contents = await avatar.read()
            file.write(contents)
        logger.info(f"Avatar uploaded for Telegram ID {telegram_id}: {filename}")
        return {"status": "success", "message": "Профиль успешно обновлен", "avatar_url": f'/uploads/{filename}'}
    except Exception as e:
        logger.error(f"Ошибка при обновлении профиля: {str(e)}")
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=400)

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting server on port 8080")
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="debug")
