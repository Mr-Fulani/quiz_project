#!/usr/bin/env bash
set -e

# Получаем параметры БД из переменных окружения или используем значения по умолчанию
DB_HOST=${DB_HOST:-postgres_db}
DB_PORT=${DB_PORT:-5432}
DB_USER=${DB_USER:-admin_fulani_quiz}
DB_NAME=${DB_NAME:-fulani_quiz_db}

echo "=== [ENTRYPOINT] Ожидание базы данных ==="
echo "Параметры подключения: host=$DB_HOST, port=$DB_PORT, user=$DB_USER, db=$DB_NAME"

until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME"; do
    echo "База данных не готова, ждём..."
    sleep 2
done

echo "✅ База данных готова!"

echo "=== [ENTRYPOINT] Запускаем Telegram-бота ==="
cd /quiz_project/bot
exec python main.py