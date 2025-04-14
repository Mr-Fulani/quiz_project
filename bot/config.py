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






# Настройки AWS S3 (если используется для хранения изображений)
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
S3_REGION = os.getenv("S3_REGION")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")




# Конфигурация базы данных
DATABASE_URL = os.getenv('DATABASE_URL')



MAKE_WEBHOOK_TIMEOUT = int(os.getenv("MAKE_WEBHOOK_TIMEOUT", 10))  # Таймаут в секундах
MAKE_WEBHOOK_RETRIES = int(os.getenv("MAKE_WEBHOOK_RETRIES", 3))
MAKE_WEBHOOK_RETRY_DELAY = int(os.getenv("MAKE_WEBHOOK_RETRY_DELAY", 5))  # Задержка между попытками в секундах







