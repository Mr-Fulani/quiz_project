#!/bin/bash

# Скрипт для полной пересборки с обновлением переменных окружения
echo "🔄 Полная пересборка с обновлением .env..."
echo ""

echo "🔌 Остановка и удаление существующих контейнеров..."
# Принудительно останавливаем все контейнеры проекта
docker compose down --volumes --remove-orphans
# Дополнительная очистка на случай конфликтов портов
docker stop $(docker ps -q --filter "name=quiz_project") 2>/dev/null || true
docker rm $(docker ps -aq --filter "name=quiz_project") 2>/dev/null || true

echo "🧹 Очистка неиспользуемых Docker-образов..."
docker image prune -f

echo "🚀 Пересборка и пересоздание всех сервисов..."
# Полная пересборка с принудительным пересозданием контейнеров
# Это обновит все переменные окружения из .env
docker compose up --build --force-recreate -d

echo "⏳ Ожидание запуска сервисов..."
sleep 10

echo "🔄 Применение миграций базы данных..."
# Выполняем миграции в контейнере quiz_backend
docker compose exec -T quiz_backend python manage.py makemigrations
docker compose exec -T quiz_backend python manage.py migrate

echo "📋 Показ логов в реальном времени..."
echo "   Для остановки нажмите Ctrl+C"
echo ""

echo "✅ Полная пересборка завершена!"
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

