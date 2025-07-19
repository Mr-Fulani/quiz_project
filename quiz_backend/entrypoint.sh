#!/bin/bash

# Entrypoint для Django приложения
# Автоматически выполняет миграции, собирает статику и загружает иконки

set -e

echo "🚀 Запуск Django приложения..."

# Ждем готовности базы данных
echo "⏳ Ожидание готовности базы данных..."
python manage.py wait_for_db

# Применяем миграции
echo "🔄 Применение миграций..."
python manage.py migrate

# Собираем статику
echo "📁 Сбор статических файлов..."
python manage.py collectstatic --noinput

# Загружаем иконки для тем
echo "🎨 Загрузка иконок для тем..."
python manage.py fix_icon_mapping

# Запускаем сервер
echo "🌐 Запуск Django сервера..."
exec python manage.py runserver 0.0.0.0:8000 