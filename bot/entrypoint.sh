#!/usr/bin/env bash
set -e

echo "=== [ENTRYPOINT] Ожидание базы данных ==="
until pg_isready -h postgres_db -p 5432 -U admin_fulani_quiz -d fulani_quiz_db; do
    echo "База данных не готова, ждём..."
    sleep 2
done

echo "=== [ENTRYPOINT] Запускаем Telegram-бота ==="
cd /quiz_project/bot
exec python main.py