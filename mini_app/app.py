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
from core.telegram_auth import init_data_for_read, request_host_headers, request_init_data, tenant_host_headers
from utils.cache_buster import get_js_url, get_css_url # Импортируем get_js_url и get_css_url
from core.config import settings

# Создаём экземпляр FastAPI (debug=False: трейсбеки не отдаются клиенту)
app = FastAPI(debug=False)

# Настраиваем логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Добавляем middleware для языка (должен быть первым)
app.add_middleware(LanguageMiddleware)


@app.middleware("http")
async def bind_init_data(request, call_next):
    """Подписанный initData текущего запроса — для пересылки в Django при серверном рендере."""
    token = request_init_data.set(init_data_for_read(request))
    host_token = request_host_headers.set(tenant_host_headers(request))
    try:
        return await call_next(request)
    finally:
        request_init_data.reset(token)
        request_host_headers.reset(host_token)

# CORS: мини-апп работает на своём домене (same-origin), поэтому чужим сайтам доступ
# не открываем. Дополнительные источники — через CORS_ALLOWED_ORIGINS (через запятую).
cors_allowed_origins = [
    origin.strip()
    for origin in os.getenv('CORS_ALLOWED_ORIGINS', '').split(',')
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роутеры
app.include_router(pages_router.router)
app.include_router(api_router.router)

# Делаем функции get_js_url и get_css_url доступными в шаблонах Jinja2
pages_router.templates.env.globals['get_js_url'] = get_js_url
pages_router.templates.env.globals['get_css_url'] = get_css_url
pages_router.templates.env.globals['dev_test_telegram_id'] = settings.DEV_TEST_TELEGRAM_ID

# Монтируем папку static как /static
current_dir = os.path.dirname(__file__)
static_dir = os.path.join(current_dir, 'static')
app.mount("/static", StaticFiles(directory=static_dir), name="static")



logger.info("Mini App is configured and ready to start.")
