#!/usr/bin/env bash
set -e

echo "=== [ENTRYPOINT] Запускаем Alembic миграции (synchronously) ==="
alembic upgrade head

echo "=== [ENTRYPOINT] Миграции ОК. Запускаем Telegram-бота ==="
exec python bot/main.py