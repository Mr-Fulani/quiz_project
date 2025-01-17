#!/usr/bin/env bash
set -e

DJANGO_MANAGE_PATH="/quiz_project/django_project/manage.py"

if [ ! -f "$DJANGO_MANAGE_PATH" ]; then
    echo "=== [ENTRYPOINT] Ошибка: Файл manage.py не найден по пути $DJANGO_MANAGE_PATH ==="
    exit 1
fi

echo "=== [ENTRYPOINT] Применение миграций Django ==="
python "$DJANGO_MANAGE_PATH" migrate

echo "=== [ENTRYPOINT] Запускаем Telegram-бота ==="
exec python bot/main.py