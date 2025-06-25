# quiz_project/mini_app/app.py

from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import logging
import os
import httpx
import asyncio
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

# Настройки для подключения к Django API
DJANGO_API_BASE_URL = "http://quiz_backend:8000"  # Адрес Django сервера в Docker сети
DJANGO_TOPICS_ENDPOINT = f"{DJANGO_API_BASE_URL}/api/simple/"  # Исправленный URL
DJANGO_API_TOKEN = os.getenv('DJANGO_API_TOKEN', '')  # Токен из переменной окружения

# PostgreSQL подключение больше не нужно - используем Django API

# Включаем CORS (разрешаем доступ с любых доменов)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Разрешить все домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Прямое подключение к БД больше не нужно - используем Django API



# Функция для получения подтем из Django API
async def fetch_subtopics_from_django(topic_id: int):
    """
    Получает список подтем для указанной темы из Django API
    """
    logger.info(f"Fetching subtopics for topic_id: {topic_id}")
    
    try:
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': f'Token {DJANGO_API_TOKEN}' if DJANGO_API_TOKEN else '',
        }
        
        # Пробуем получить подтемы из Django API
        subtopics_url = f"{DJANGO_API_BASE_URL}/api/{topic_id}/subtopics/"
        logger.info(f"Requesting subtopics from: {subtopics_url}")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(subtopics_url, headers=headers, timeout=10.0)
            logger.info(f"Subtopics API response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Got subtopics from API: {data}")
                return data if isinstance(data, list) else data.get('results', data)
            else:
                logger.warning(f"Subtopics API returned {response.status_code}, using fallback data")
                return get_fallback_subtopics(topic_id)
                
    except Exception as e:
        logger.error(f"Ошибка при получении подтем: {e}")
        return get_fallback_subtopics(topic_id)

# Fallback данные для подтем
def get_fallback_subtopics(topic_id: int):
    """
    Резервные данные подтем на случай недоступности Django API
    """
    fallback_data = {
        8: [  # Python
            {"id": 1, "name": "Синтаксис", "questions_count": 8},
            {"id": 2, "name": "Структуры данных", "questions_count": 6},
            {"id": 3, "name": "ООП", "questions_count": 7},
            {"id": 4, "name": "Библиотеки", "questions_count": 5}
        ],
        9: [  # JavaScript
            {"id": 5, "name": "DOM", "questions_count": 5},
            {"id": 6, "name": "Async/Await", "questions_count": 4},
            {"id": 7, "name": "ES6+", "questions_count": 6},
            {"id": 8, "name": "Frameworks", "questions_count": 5}
        ],
        10: [  # React
            {"id": 9, "name": "Компоненты", "questions_count": 8},
            {"id": 10, "name": "Hooks", "questions_count": 7},
            {"id": 11, "name": "State Management", "questions_count": 6},
            {"id": 12, "name": "Router", "questions_count": 4}
        ],
        11: [  # SQL
            {"id": 13, "name": "SELECT запросы", "questions_count": 6},
            {"id": 14, "name": "JOIN операции", "questions_count": 5},
            {"id": 15, "name": "Индексы", "questions_count": 4},
            {"id": 16, "name": "Процедуры", "questions_count": 3}
        ],
        13: [  # Django
            {"id": 17, "name": "Модели и ORM", "questions_count": 6},
            {"id": 18, "name": "Views и URLs", "questions_count": 5},
            {"id": 19, "name": "Templates", "questions_count": 4},
            {"id": 20, "name": "Forms", "questions_count": 5}
        ],
        14: [  # Docker
            {"id": 21, "name": "Контейнеры", "questions_count": 7},
            {"id": 22, "name": "Docker Compose", "questions_count": 6},
            {"id": 23, "name": "Volumes", "questions_count": 4},
            {"id": 24, "name": "Networks", "questions_count": 3}
        ],
        15: [  # Git
            {"id": 25, "name": "Основные команды", "questions_count": 8},
            {"id": 26, "name": "Ветки", "questions_count": 5},
            {"id": 27, "name": "Merge и Rebase", "questions_count": 4},
            {"id": 28, "name": "Remote репозитории", "questions_count": 3}
        ],
        16: [  # Golang
            {"id": 29, "name": "Goroutines", "questions_count": 7},
            {"id": 30, "name": "Channels", "questions_count": 5},
            {"id": 31, "name": "Interfaces", "questions_count": 6},
            {"id": 32, "name": "Packages", "questions_count": 4}
        ]
    }
    
    logger.info(f"Getting fallback subtopics for topic_id: {topic_id}")
    result = fallback_data.get(topic_id, [])
    logger.info(f"Returning {len(result)} subtopics for topic {topic_id}")
    return result

# Функция для получения тем из Django API
async def fetch_topics_from_django(search: str = None):
    """
    Получает список тем из Django API
    """
    try:
        params = {}
        if search:
            params['search'] = search
            
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': f'Token {DJANGO_API_TOKEN}' if DJANGO_API_TOKEN else '',
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(DJANGO_TOPICS_ENDPOINT, params=params, headers=headers, timeout=10.0)
            response.raise_for_status()
            data = response.json()
            # Django API возвращает список напрямую, не объект с 'results'
            return data if isinstance(data, list) else data.get('results', data)
    except httpx.RequestError as e:
        logger.error(f"Ошибка подключения к Django API: {e}")
        # Fallback на статические данные
        return get_fallback_topics()
    except httpx.HTTPStatusError as e:
        logger.error(f"Django API вернул ошибку {e.response.status_code}: {e.response.text}")
        return get_fallback_topics()
    except Exception as e:
        logger.error(f"Неожиданная ошибка при обращении к Django API: {e}")
        return get_fallback_topics()

# Fallback данные на случай недоступности Django API
def get_fallback_topics():
    """
    Резервные статические данные тем на случай недоступности Django API
    """
    return [
        {
            "id": 1,
            "name": "Python",
            "description": "Тестирование знаний Python",
            "image_url": "https://picsum.photos/400/400?1",
            "difficulty": "Средний",
            "questions_count": 25
        },
        {
            "id": 2,
            "name": "JavaScript", 
            "description": "Основы JavaScript",
            "image_url": "https://picsum.photos/400/400?2",
            "difficulty": "Легкий",
            "questions_count": 20
        },
        {
            "id": 3,
            "name": "React",
            "description": "React фреймворк",
            "image_url": "https://picsum.photos/400/400?3", 
            "difficulty": "Сложный",
            "questions_count": 30
        },
        {
            "id": 4,
            "name": "SQL",
            "description": "Базы данных SQL",
            "image_url": "https://picsum.photos/400/400?4",
            "difficulty": "Средний", 
            "questions_count": 22
        }
    ]

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
async def index(request: Request, search: str = None):
    logger.info("Rendering index page")
    topics = await fetch_topics_from_django(search)
    return templates.TemplateResponse("index.html", {"request": request, "topics": topics})

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

# Обработка страницы темы
@app.get("/topic/{topic_id}", response_class=HTMLResponse)
async def topic_detail(request: Request, topic_id: int):
    logger.info(f"Rendering topic detail page for topic {topic_id}")
    topics = await fetch_topics_from_django()
    topic = next((t for t in topics if t["id"] == topic_id), None)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    
    # Получаем подтемы из Django API
    subtopics = await fetch_subtopics_from_django(topic_id)
    logger.info(f"Got {len(subtopics)} subtopics for topic {topic_id}")
    topic["subtopics"] = subtopics
    
    logger.info(f"Final topic data: {topic}")
    return templates.TemplateResponse("topic_detail.html", {"request": request, "topic": topic})

# API для получения тем
@app.get("/api/topics")
async def get_topics(search: str = None):
    logger.info("API request for topics")
    # Используем Django API вместо прямого подключения к БД
    topics = await fetch_topics_from_django(search)
    return {"topics": topics}

# API для получения конкретной темы
@app.get("/api/topic/{topic_id}")
async def get_topic(topic_id: int):
    logger.info(f"API request for topic {topic_id}")
    topics = await fetch_topics_from_django()
    topic = next((t for t in topics if t["id"] == topic_id), None)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    return {"topic": topic}

# API для получения статистики профиля (прокси к Django)
@app.get("/api/profile/stats")
async def get_profile_stats():
    """Быстрый прокси endpoint для получения статистики профиля из Django API"""
    try:
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': f'Token {DJANGO_API_TOKEN}',
            'Host': 'localhost:8001',
        }
        
        django_url = f"{DJANGO_API_BASE_URL}/api/profile/stats/"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(django_url, headers=headers, timeout=5.0)
            
            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(status_code=response.status_code, detail="API error")
                
    except httpx.RequestError:
        # Быстрый fallback без логов
        return {
            "user": {"telegram_id": 12345, "username": "user", "first_name": "User", "last_name": "", "avatar_url": None},
            "stats": {"total_quizzes": 0, "completed_quizzes": 0, "success_rate": 0, "total_points": 0, "current_streak": 0, "best_streak": 0},
            "topic_progress": [],
            "achievements": []
        }
    except Exception:
        raise HTTPException(status_code=500, detail="Server error")

# API для получения полного профиля пользователя
@app.get("/api/profile/full")
async def get_full_profile():
    """Получение полного профиля пользователя включая социальные сети"""
    try:
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': f'Token {DJANGO_API_TOKEN}',
        }
        
        django_url = f"{DJANGO_API_BASE_URL}/api/profile/"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(django_url, headers=headers, timeout=5.0)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Django profile API error: {response.status_code}")
                # Возвращаем fallback только при ошибке API
                return {
                    "id": 1,
                    "username": "demo_user",
                    "email": "demo@example.com",
                    "first_name": "Demo",
                    "last_name": "User",
                    "bio": "Пример пользователя",
                    "location": "Москва",
                    "website": "https://example.com",
                    "telegram": "https://t.me/demo_user",
                    "github": "https://github.com/demo_user", 
                    "linkedin": "",
                    "instagram": "",
                    "facebook": "",
                    "youtube": "",
                    "avatar_url": "/static/images/default_avatar.png",
                    "theme_preference": "dark",
                    "is_public": True,
                    "total_points": 150,
                    "quizzes_completed": 5
                }
                
    except Exception as e:
        logger.error(f"Connection error to Django: {e}")
        # Fallback данные только при сетевых ошибках
        return {
            "id": 1,
            "username": "demo_user",
            "email": "demo@example.com",
            "first_name": "Demo",
            "last_name": "User",
            "bio": "Пример пользователя",
            "location": "Москва",
            "website": "https://example.com",
            "telegram": "https://t.me/demo_user",
            "github": "https://github.com/demo_user", 
            "linkedin": "",
            "instagram": "",
            "facebook": "",
            "youtube": "",
            "avatar_url": "/static/images/default_avatar.png",
            "theme_preference": "dark",
            "is_public": True,
            "total_points": 150,
            "quizzes_completed": 5
        }

# API для обновления социальных сетей
@app.patch("/api/profile/social-links")
async def update_social_links(social_data: dict):
    """Обновление социальных сетей пользователя"""
    try:
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': f'Token {DJANGO_API_TOKEN}',
        }
        
        django_url = f"{DJANGO_API_BASE_URL}/api/social-links/"
        
        async with httpx.AsyncClient() as client:
            response = await client.patch(django_url, json=social_data, headers=headers, timeout=5.0)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Django API error {response.status_code}")
                # Возвращаем ошибку пользователю
                raise HTTPException(status_code=response.status_code, detail=f"Django API error: {response.status_code}")
                
    except httpx.RequestError as e:
        logger.error(f"Connection error to Django: {e}")
        raise HTTPException(status_code=503, detail="Django service unavailable")
    except HTTPException:
        raise  # Перебрасываем HTTPException как есть
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting server on port 8080")
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="debug")
