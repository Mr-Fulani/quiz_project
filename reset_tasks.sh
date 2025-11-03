#!/bin/bash
# Скрипт для выполнения сброса задач через Docker

# Цвета для вывода
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo -e "${YELLOW}⚠️  ВНИМАНИЕ: Это удалит ВСЕ задачи из базы данных!${NC}"
read -p "Вы уверены? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo -e "${RED}Операция отменена${NC}"
    exit 1
fi

# Определяем имя контейнера БД
DB_CONTAINER="postgres_db_local_prod"
DB_NAME="${DB_NAME:-fulani_quiz_db}"
DB_USER="${DB_USER:-postgres}"

echo -e "${YELLOW}Выполнение SQL команд...${NC}"

# Выполняем SQL команды
docker compose -f docker-compose.local-prod.yml exec -T $DB_CONTAINER psql -U $DB_USER -d $DB_NAME <<EOF
-- Удаляем все задачи
DELETE FROM tasks;

-- Сбрасываем счетчики
ALTER SEQUENCE tasks_id_seq RESTART WITH 1;
ALTER SEQUENCE task_translations_id_seq RESTART WITH 1;
ALTER SEQUENCE task_statistics_id_seq RESTART WITH 1;
ALTER SEQUENCE task_polls_id_seq RESTART WITH 1;
EOF

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Все задачи удалены, счетчики ID сброшены!${NC}"
else
    echo -e "${RED}❌ Ошибка при выполнении команд${NC}"
    exit 1
fi

