#!/usr/bin/env bash
set -e

echo "=== [ENTRYPOINT] Проверка состояния Alembic миграций ==="
alembic current

echo "=== [ENTRYPOINT] Запускаем Alembic миграции ==="
alembic upgrade head || echo "Миграции уже применены."

echo "=== [ENTRYPOINT] Запускаем Telegram-бота ==="
exec python bot/main.py