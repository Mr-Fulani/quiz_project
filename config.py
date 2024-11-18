# config.py

import json
import os
from dotenv import load_dotenv
import logging



load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Установите уровень логирования



# Токены ботов
PUBLICATION_BOT_TOKEN = os.getenv("PUBLICATION_BOT_TOKEN")
WEBHOOK_BOT_TOKEN = os.getenv('WEBHOOK_BOT_TOKEN')



# Целевой Chat ID для публикации
TARGET_CHAT_ID = os.getenv("TARGET_CHAT_ID")




# Настройки AWS S3 (если используется для хранения изображений)
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
S3_REGION = os.getenv("S3_REGION")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")




# Конфигурация базы данных
DATABASE_URL = os.getenv('DATABASE_URL')



# Настройки клиента вебхука (отправка данных на внешние сервисы)
MAKE_WEBHOOK_URL = os.getenv("MAKE_WEBHOOK_URL")
MAKE_WEBHOOK_TIMEOUT = int(os.getenv("MAKE_WEBHOOK_TIMEOUT", 10))  # Таймаут в секундах
MAKE_WEBHOOK_RETRIES = int(os.getenv("MAKE_WEBHOOK_RETRIES", 3))
MAKE_WEBHOOK_RETRY_DELAY = int(os.getenv("MAKE_WEBHOOK_RETRY_DELAY", 5))  # Задержка между попытками в секундах



# Разрешённые пользователи (если требуется)
ALLOWED_USERS = json.loads(os.getenv("ALLOWED_USERS", "[]"))



# Временное логирование для отладки
logger.debug(f"PUBLICATION_BOT_TOKEN: {PUBLICATION_BOT_TOKEN}")
logger.debug(f"WEBHOOK_BOT_TOKEN: {WEBHOOK_BOT_TOKEN}")
logger.debug(f"TARGET_CHAT_ID: {TARGET_CHAT_ID}")
logger.debug(f"S3_BUCKET_NAME: {S3_BUCKET_NAME}")
logger.debug(f"S3_REGION: {S3_REGION}")
logger.debug(f"AWS_ACCESS_KEY_ID: {AWS_ACCESS_KEY_ID}")
logger.debug(f"AWS_SECRET_ACCESS_KEY: {AWS_SECRET_ACCESS_KEY}")
logger.debug(f"DATABASE_URL: {DATABASE_URL}")
logger.debug(f"MAKE_WEBHOOK_URL: {MAKE_WEBHOOK_URL}")
logger.debug(f"MAKE_WEBHOOK_TIMEOUT: {MAKE_WEBHOOK_TIMEOUT}")
logger.debug(f"MAKE_WEBHOOK_RETRIES: {MAKE_WEBHOOK_RETRIES}")
logger.debug(f"MAKE_WEBHOOK_RETRY_DELAY: {MAKE_WEBHOOK_RETRY_DELAY}")
logger.debug(f"ALLOWED_USERS: {ALLOWED_USERS}")