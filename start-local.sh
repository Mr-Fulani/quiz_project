#!/bin/bash

export CURRENT_UID=$(id -u)
export CURRENT_GID=$(id -g)

# Скрипт для локальной разработки
echo "🔧 Запуск локальной разработки..."

echo "🔌 Остановка и удаление существующих контейнеров..."
docker compose down --volumes

echo "🚀 Запуск всех сервисов для локальной разработки..."
# Запускаем все сервисы с локальной конфигурацией
docker compose up -d --build

echo "✅ Локальная разработка запущена!"
echo ""
echo "🌐 Доступные сервисы:"
echo "  - Backend: http://localhost:8001"
echo "  - Mini App: http://localhost:8080"
echo "  - Telegram Bot: http://localhost:8002"
echo "  - Database: localhost:5433"
echo ""
echo "📝 Для остановки: docker compose down"