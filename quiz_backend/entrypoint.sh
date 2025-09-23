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

# Создаем папку staticfiles если её нет
echo "📁 Создание папки staticfiles..."
mkdir -p staticfiles

# Устанавливаем правильные права доступа
echo "🔐 Установка прав доступа для staticfiles..."
chmod -R 755 staticfiles

# Очищаем старую статику перед сбором
echo "🧹 Очистка старых статических файлов..."
rm -rf staticfiles/*

# Собираем статику
echo "📁 Сбор статических файлов..."
python manage.py collectstatic --noinput --clear

# Проверяем, что статика собралась
echo "🔍 Проверка собранных статических файлов..."
if [ -d "staticfiles" ] && [ "$(ls -A staticfiles)" ]; then
    echo "✅ Статические файлы успешно собраны"
    ls -la staticfiles/ | head -10
    
    # Устанавливаем права доступа после сборки
    echo "🔐 Установка прав доступа после сборки..."
    chmod -R 755 staticfiles
    
    # Проверяем права доступа
    echo "🔍 Проверка прав доступа..."
    ls -la staticfiles/ | head -5
else
    echo "❌ Ошибка: статические файлы не собраны"
    exit 1
fi

# Загружаем иконки для тем
echo "🎨 Загрузка иконок для тем..."
python manage.py fix_icon_mapping

# Запускаем сервер в зависимости от DEBUG
echo "🌐 Запуск Django сервера..."
if [ "$DEBUG" = "True" ]; then
    # Для разработки используем runserver с автоперезагрузкой
    exec python manage.py runserver 0.0.0.0:8000
else
    # Для продакшена используем Gunicorn
    exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4
fi 