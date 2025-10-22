import os
from pydantic_settings import BaseSettings

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

class Settings(BaseSettings):
    """Настройки приложения"""
    
    # Telegram Bot Token
    TELEGRAM_BOT_TOKEN: str
    
    # Admin Telegram ID для прямой связи (username без @)
    ADMIN_TELEGRAM_ID: str = ""
    
    # Django API
    DJANGO_API_BASE_URL: str = "http://nginx_local:8080"
    DJANGO_API_TOKEN: str
    
    # Локализация
    DEFAULT_LANGUAGE: str = "en"
    SUPPORTED_LANGUAGES: list = ["en", "ru"]
    
    # Настройки приложения
    APP_NAME: str = "Quiz Mini App"
    DEBUG: bool = True
    UPLOAD_FOLDER: str = UPLOAD_FOLDER
    
    # URL для генерации превью ссылок в продакшене
    MINI_APP_BASE_URL: str = "http://localhost:8080"

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'
        # Важно: сначала загружаем из переменных окружения, потом из .env файла
        # В Docker переменные окружения имеют приоритет
        case_sensitive = True

settings = Settings()

# Логирование для отладки
import logging
logger = logging.getLogger(__name__)
logger.info(f"✅ Settings loaded: ADMIN_TELEGRAM_ID=[{settings.ADMIN_TELEGRAM_ID}]")
logger.info(f"✅ Settings loaded: TELEGRAM_BOT_TOKEN={'*' * 10 if settings.TELEGRAM_BOT_TOKEN else 'NOT SET'}")

# Настройки для подключения к Django API
DJANGO_TOPICS_ENDPOINT = f"{settings.DJANGO_API_BASE_URL}/api/simple/" 