#!/bin/bash

# Скрипт для запуска продакшена
echo "🌐 Запуск продакшена..."

# Устанавливаем переменную окружения для продакшен конфигурации
export NGINX_DOCKERFILE=Dockerfile.prod

# Запускаем контейнеры
docker-compose down && docker-compose up --build -d

echo "✅ Продакшен запущен!"
