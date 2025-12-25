#!/bin/bash

# Универсальный скрипт для локальной разработки
# Использование:
#   ./start-local-new.sh              - стандартный запуск с очисткой кэша
#   ./start-local-new.sh --clean-db   - полная очистка включая БД
#   ./start-local-new.sh --quick      - быстрый restart без пересборки

set -e

# Флаги
CLEAN_DB=false
QUICK=false

# Парсим аргументы
while [[ $# -gt 0 ]]; do
    case $1 in
        --clean-db)
            CLEAN_DB=true
            shift
            ;;
        --quick)
            QUICK=true
            shift
            ;;
        *)
            echo "❌ Неизвестный параметр: $1"
            echo ""
            echo "Использование:"
            echo "  ./start-local-new.sh              - стандартный запуск (БД сохраняется, кэш очищается)"
            echo "  ./start-local-new.sh --clean-db   - полная очистка включая БД"
            echo "  ./start-local-new.sh --quick      - быстрый restart (5 сек)"
            echo ""
            exit 1
            ;;
    esac
done

# Режим быстрого restart
if [ "$QUICK" = true ]; then
    echo "⚡ Быстрый перезапуск сервисов..."
    docker compose restart
    
    echo "✅ Сервисы перезапущены!"
    echo ""
    docker compose ps
    exit 0
fi

# Стандартный запуск
echo "🚀 Запуск локальной разработки..."
echo ""

# Останавливаем контейнеры
echo "🔌 Остановка контейнеров..."
if [ "$CLEAN_DB" = true ]; then
    echo "   ⚠️  Режим CLEAN-DB: volumes будут удалены (БД очистится!)"
    read -p "   Продолжить? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ Отменено"
        exit 0
    fi
    docker compose down --volumes --remove-orphans
else
    echo "   💾 БД будет сохранена"
    docker compose down --remove-orphans
fi

# Дополнительная очистка процессов
docker stop $(docker ps -q --filter "name=quiz_project") 2>/dev/null || true
docker rm $(docker ps -aq --filter "name=quiz_project") 2>/dev/null || true

echo "🧹 Очистка неиспользуемых Docker-образов..."
docker image prune -f

echo "🔨 Пересборка образов и запуск сервисов..."
docker compose up --build --force-recreate -d

echo "⏳ Ожидание запуска сервисов..."
sleep 10

echo "🧹 Очистка кэша Redis..."
docker compose exec -T redis redis-cli FLUSHDB || echo "   ℹ️  Redis еще не готов, пропускаем очистку"

echo "🔄 Применение миграций..."
docker compose exec -T quiz_backend python manage.py makemigrations
docker compose exec -T quiz_backend python manage.py migrate

echo "📁 Сбор статических файлов..."
docker compose exec -T quiz_backend python manage.py collectstatic --noinput --clear

echo ""
echo "🎨 Загрузка официальных логотипов языков программирования..."
# Загружаем официальные логотипы для тем (языков программирования), только если их нет
echo "  📥 Скачивание недостающих официальных иконок..."
docker compose exec -T quiz_backend python manage.py download_official_icons --delay 1

echo "  🔧 Сопоставление иконок с темами..."
docker compose exec -T quiz_backend python manage.py fix_icon_mapping

echo "  📁 Пересборка статических файлов после загрузки иконок..."
docker compose exec -T quiz_backend python manage.py collectstatic --noinput --clear

echo "✅ Логотипы языков скачаны, сопоставлены и статические файлы пересобраны"

echo ""
echo "✅ Локальная разработка готова!"
echo ""
echo "🌐 Доступные сервисы:"
echo "  - Backend: http://localhost:8001"
echo "  - Mini App: http://localhost:8080"
echo "  - Telegram Bot: http://localhost:8002"
echo "  - Database: localhost:5433"
echo "  - Redis: localhost:6379"
echo ""
echo "🔍 Статус сервисов:"
docker compose ps
echo ""
echo "📝 Полезные команды:"
echo "  - Остановить: docker compose down"
echo "  - Логи: docker compose logs -f"
echo "  - Кэш: docker compose run --rm quiz_backend python manage.py cache_monitor"
echo "  - Celery: docker compose exec celery_worker celery -A config inspect ping"
echo ""

# Спрашиваем показать ли логи
read -p "📋 Показать логи в реальном времени? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "🔍 Отображение логов (Ctrl+C для выхода)..."
    docker compose logs -f
fi

