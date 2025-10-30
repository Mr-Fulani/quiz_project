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

# Создаем директорию для логов если её нет
echo "📁 Создание папки логов..."
mkdir -p logs
chmod -R 755 logs

# Запускаем сервер в зависимости от DEBUG
echo "🌐 Запуск Django сервера..."
if [ "$DEBUG" = "True" ]; then
    # Для разработки используем runserver с автоперезагрузкой
    exec python manage.py runserver 0.0.0.0:8000
else
    # Для продакшена используем Gunicorn с оптимальными настройками
    echo "🚀 Запуск Gunicorn в продакшен режиме..."
    
    # Рассчитываем оптимальное количество workers: (2 x CPU cores) + 1
    WORKERS=${GUNICORN_WORKERS:-4}
    # Количество потоков на worker
    THREADS=${GUNICORN_THREADS:-2}
    # Таймаут для запросов
    TIMEOUT=${GUNICORN_TIMEOUT:-120}
    # Worker class (sync, gevent, eventlet)
    WORKER_CLASS=${GUNICORN_WORKER_CLASS:-sync}
    
    exec gunicorn config.wsgi:application \
        --bind 0.0.0.0:8000 \
        --workers $WORKERS \
        --threads $THREADS \
        --worker-class $WORKER_CLASS \
        --timeout $TIMEOUT \
        --max-requests 1000 \
        --max-requests-jitter 50 \
        --access-logfile /app/logs/gunicorn-access.log \
        --error-logfile /app/logs/gunicorn-error.log \
        --log-level info \
        --capture-output \
        --enable-stdio-inheritance
fi 