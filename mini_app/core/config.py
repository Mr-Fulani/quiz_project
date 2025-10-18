import os
from pydantic_settings import BaseSettings

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

class Settings(BaseSettings):
    """Настройки приложения"""
    
    # Telegram Bot Token
    TELEGRAM_BOT_TOKEN: str
    
    # Admin Telegram ID для прямой связи
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
    
    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'

settings = Settings()

# Настройки для подключения к Django API
DJANGO_TOPICS_ENDPOINT = f"{settings.DJANGO_API_BASE_URL}/api/simple/" 