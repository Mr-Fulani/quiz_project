import os

# Настройки мини-приложения
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", 5000))
DEBUG = os.getenv("DEBUG", "true").lower() == "true"