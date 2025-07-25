import os
from pydantic_settings import BaseSettings

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

class Settings(BaseSettings):
    TELEGRAM_BOT_TOKEN: str
    DJANGO_API_BASE_URL: str
    DJANGO_API_TOKEN: str
    UPLOAD_FOLDER: str = UPLOAD_FOLDER

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'

settings = Settings()

# Настройки для подключения к Django API
DJANGO_TOPICS_ENDPOINT = f"{settings.DJANGO_API_BASE_URL}/api/simple/" 