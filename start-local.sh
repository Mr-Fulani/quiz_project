#!/bin/bash

# Скрипт для запуска локальной разработки
echo "🏠 Запуск локальной разработки..."

# Устанавливаем переменную окружения для локальной конфигурации
export NGINX_DOCKERFILE=Dockerfile

# Запускаем контейнеры
docker-compose down && docker-compose up --build

echo "✅ Локальная разработка запущена!"
