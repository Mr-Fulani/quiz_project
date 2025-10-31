#!/bin/bash

# Entrypoint для Django приложения
# Автоматически выполняет миграции, собирает статику и загружает иконки

# КРИТИЧЕСКИЕ операции - должны выполняться с обязательной проверкой ошибок
set -e

echo "🚀 Запуск Django приложения..."

# Ждем готовности базы данных
echo "⏳ Ожидание готовности базы данных..."
python manage.py wait_for_db

# Применяем миграции
echo "🔄 Применение миграций..."
python manage.py migrate

# Отключаем set -e для некритических операций
set +e

# Создаем папку staticfiles если её нет
echo "📁 Создание папки staticfiles..."
mkdir -p staticfiles

# Устанавливаем правильные права доступа
echo "🔐 Установка прав доступа для staticfiles..."
chmod -R 755 staticfiles

# Только собираем статику БЕЗ очистки (очистка уже выполнена в start-prod.sh)
# Это значительно ускоряет запуск контейнера на продакшене
echo "📁 Сбор статических файлов..."
python manage.py collectstatic --noinput || {
    echo "⚠️  Предупреждение: collectstatic завершился с ошибкой, но продолжаем запуск"
}

# Проверяем, что статика собралась
if [ -d "staticfiles" ] && [ "$(ls -A staticfiles 2>/dev/null)" ]; then
    echo "✅ Статические файлы готовы"
    chmod -R 755 staticfiles
else
    echo "⚠️  Предупреждение: staticfiles пуст или недоступен, но продолжаем запуск"
fi

# Загружаем иконки для тем в фоновом режиме (необязательная операция)
echo "🎨 Загрузка иконок для тем в фоновом режиме..."
(python manage.py fix_icon_mapping 2>&1 || echo "⚠️  Не удалось загрузить иконки") &
ICON_PID=$!
# Даем немного времени, но не ждем окончания
sleep 3
# Убиваем процесс если он еще работает (не ждем долго)
kill $ICON_PID 2>/dev/null || true
echo "✅ Инициализация завершена"

# Создаем директорию для логов если её нет
echo "📁 Создание папки логов..."
mkdir -p logs
chmod -R 755 logs

# Возвращаем set -e для запуска сервера (критическая операция)
set -e

# Запускаем сервер в зависимости от DEBUG
echo "🌐 Запуск Django сервера..."
if [ "$DEBUG" = "True" ]; then
    # Для разработки используем runserver с автоперезагрузкой
    exec python manage.py runserver 0.0.0.0:8000
else
    # Для продакшена используем Gunicorn с оптимальными настройками
    echo "🚀 Запуск Gunicorn в продакшен режиме..."
    
    # Рассчитываем оптимальное количество workers (по умолчанию 2 для слабых серверов)
    WORKERS=${GUNICORN_WORKERS:-2}
    THREADS=${GUNICORN_THREADS:-2}
    TIMEOUT=${GUNICORN_TIMEOUT:-120}
    WORKER_CLASS=${GUNICORN_WORKER_CLASS:-sync}
    
    echo "⚙️  Настройки Gunicorn: workers=$WORKERS, threads=$THREADS, timeout=$TIMEOUT"
    
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