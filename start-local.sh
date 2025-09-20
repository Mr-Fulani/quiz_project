#!/bin/bash

# Устанавливаем переменные окружения для Docker
export CURRENT_UID=$(id -u)
export CURRENT_GID=$(id -g)

# Скрипт для локальной разработки
echo "🔧 Запуск локальной разработки..."

echo "🔌 Остановка и удаление существующих контейнеров..."
docker compose down --volumes

echo "🧹 Очистка неиспользуемых Docker-образов..."
docker image prune -f

echo "🚀 Запуск всех сервисов для локальной разработки..."
# Запускаем все сервисы в фоновом режиме
docker compose up --build -d

echo "⏳ Ожидание запуска сервисов..."
sleep 5

echo "📋 Показ логов в реальном времени..."
echo "   Для остановки нажмите Ctrl+C"
echo ""

echo "✅ Локальная разработка запущена!"
echo ""
echo "🌐 Доступные сервисы:"
echo "  - Backend: http://localhost:8001"
echo "  - Mini App: http://localhost:8080"
echo "  - Telegram Bot: http://localhost:8002"
echo "  - Database: localhost:5433"
echo ""
echo "📝 Для остановки: docker compose down"
echo ""

# Показываем логи всех сервисов в реальном времени
docker compose logs -f