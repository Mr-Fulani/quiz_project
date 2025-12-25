#!/bin/bash

# Скрипт для создания squash миграций
# Это решит проблему синхронизации миграций между локальным и продакшеном

echo "🔄 Создание squash миграций для синхронизации..."

# Активируем виртуальное окружение
source .venv/bin/activate

cd quiz_backend

# Создаем squash миграции для каждого приложения
echo "📦 Создание squash миграции для accounts..."
python manage.py squashmigrations accounts 0001 0015 --noinput

echo "📦 Создание squash миграции для blog..."
python manage.py squashmigrations blog 0001 0011 --noinput

echo "📦 Создание squash миграции для donation..."
python manage.py squashmigrations donation 0001 0006 --noinput

echo "📦 Создание squash миграции для feedback..."
python manage.py squashmigrations feedback 0001 0006 --noinput

echo "📦 Создание squash миграции для platforms..."
python manage.py squashmigrations platforms 0001 0002 --noinput

echo "📦 Создание squash миграции для social_auth..."
python manage.py squashmigrations social_auth 0001 0003 --noinput

echo "📦 Создание squash миграции для tasks..."
python manage.py squashmigrations tasks 0001 0012 --noinput

echo "📦 Создание squash миграции для topics..."
python manage.py squashmigrations topics 0001 0004 --noinput

echo "📦 Создание squash миграции для webhooks..."
python manage.py squashmigrations webhooks 0001 0005 --noinput

echo "✅ Squash миграции созданы!"
echo ""
echo "📋 Следующие шаги:"
echo "1. Удалите старые миграции (все кроме __init__.py и новой squash миграции)"
echo "2. Сделайте коммит squash миграций"
echo "3. На сервере примените новые squash миграции"
echo ""
echo "⚠️  Важно: Перед запуском убедитесь, что на сервере нет непримененных миграций!"
