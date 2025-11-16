#!/usr/bin/env bash
set -e

# Получаем параметры БД из переменных окружения или используем значения по умолчанию
DB_HOST=${DB_HOST:-postgres_db}
DB_PORT=${DB_PORT:-5432}
DB_USER=${DB_USER:-postgres}
DB_NAME=${DB_NAME:-fulani_quiz_db}

# Автоматическое определение хоста БД, если не указан явно
# Проверяем доступность разных вариантов имени хоста
if [ -z "$DB_HOST" ] || [ "$DB_HOST" = "database" ]; then
    # Пробуем подключиться к разным вариантам имени хоста
    if pg_isready -h "postgres_db_local_prod" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" 2>/dev/null; then
        DB_HOST="postgres_db_local_prod"
    elif pg_isready -h "postgres_db" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" 2>/dev/null; then
        DB_HOST="postgres_db"
    fi
fi

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