#!/usr/bin/env bash
set -e

DJANGO_MANAGE_PATH="/quiz_project/quiz_backend/manage.py"

if [ ! -f "$DJANGO_MANAGE_PATH" ]; then
    echo "=== [ENTRYPOINT] Ошибка: Файл manage.py не найден по пути $DJANGO_MANAGE_PATH ==="
    exit 1
fi

echo "=== [ENTRYPOINT] Применение миграций Django ==="
python "$DJANGO_MANAGE_PATH" migrate

echo "=== [ENTRYPOINT] Запускаем Telegram-бота ==="
cd /quiz_project/bot
exec python main.py