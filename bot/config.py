# config.py

import json
import os
from dotenv import load_dotenv
import logging



load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Установите уровень логирования



# Токены ботов
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

ADMIN_SECRET_PASSWORD = os.getenv("ADMIN_SECRET_PASSWORD")
ADMIN_REMOVE_SECRET_PASSWORD = os.getenv("ADMIN_REMOVE_SECRET_PASSWORD")  # Новый пароль






# Настройки Cloudflare R2 / AWS S3 (для хранения изображений и видео)
USE_R2_STORAGE = os.getenv("USE_R2_STORAGE", "False").lower() == "true"

# Определяем окружение для бота (prod или dev)
# Можно переопределить через переменную окружения, иначе используем dev по умолчанию для бота
BOT_ENV = os.getenv("BOT_ENV", "dev").lower()  # dev или prod
R2_ENVIRONMENT_PREFIX = BOT_ENV if BOT_ENV in ['dev', 'prod'] else 'dev'

if USE_R2_STORAGE:
    # Настройки Cloudflare R2
    R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
    R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
    R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
    R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "quiz-hub-prod")
    R2_PUBLIC_DOMAIN = os.getenv("R2_PUBLIC_DOMAIN")
    
    # Используем R2 credentials
    S3_BUCKET_NAME = R2_BUCKET_NAME
    S3_REGION = "auto"  # R2 не требует region, но используем 'auto' для совместимости
    AWS_ACCESS_KEY_ID = R2_ACCESS_KEY_ID
    AWS_SECRET_ACCESS_KEY = R2_SECRET_ACCESS_KEY
    
    # R2 endpoint URL
    if R2_ACCOUNT_ID:
        R2_ENDPOINT_URL = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
    else:
        R2_ENDPOINT_URL = None
        logger.warning("R2_ACCOUNT_ID не установлен, endpoint URL не будет использоваться")
    
    logger.info(f"R2 хранилище настроено для бота: бакет={R2_BUCKET_NAME}, окружение={R2_ENVIRONMENT_PREFIX}")
else:
    # Настройки AWS S3 (старые, для обратной совместимости)
    S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
    S3_REGION = os.getenv("S3_REGION")
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    R2_ENDPOINT_URL = None
    R2_ENVIRONMENT_PREFIX = None




# Конфигурация базы данных
DATABASE_URL = os.getenv('DATABASE_URL')



MAKE_WEBHOOK_TIMEOUT = int(os.getenv("MAKE_WEBHOOK_TIMEOUT", 10))  # Таймаут в секундах
MAKE_WEBHOOK_RETRIES = int(os.getenv("MAKE_WEBHOOK_RETRIES", 3))
MAKE_WEBHOOK_RETRY_DELAY = int(os.getenv("MAKE_WEBHOOK_RETRY_DELAY", 5))  # Задержка между попытками в секундах







