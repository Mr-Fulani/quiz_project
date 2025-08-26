# quiz_project/mini_app/app.py

import logging
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# Импортируем наши роутеры
from routers import api as api_router
from routers import pages as pages_router
from middleware.language_middleware import LanguageMiddleware
from utils.cache_buster import get_js_url, get_css_url # Импортируем get_js_url и get_css_url

# Создаём экземпляр FastAPI
app = FastAPI(debug=True)

# Настраиваем логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Добавляем middleware для языка (должен быть первым)
app.add_middleware(LanguageMiddleware)

# Включаем CORS (разрешаем доступ с любых доменов)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роутеры
app.include_router(pages_router.router)
app.include_router(api_router.router)

# Делаем функции get_js_url и get_css_url доступными в шаблонах Jinja2
pages_router.templates.env.globals['get_js_url'] = get_js_url
pages_router.templates.env.globals['get_css_url'] = get_css_url

# Монтируем папку static как /static
current_dir = os.path.dirname(__file__)
static_dir = os.path.join(current_dir, 'static')
app.mount("/static", StaticFiles(directory=static_dir), name="static")



logger.info("Mini App is configured and ready to start.")
