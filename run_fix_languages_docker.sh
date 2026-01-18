#!/bin/bash

# Скрипт для запуска исправления языков в Docker контейнере
# Использование:
#   ./run_fix_languages_docker.sh --dry-run  # анализ
#   ./run_fix_languages_docker.sh --fix      # исправление

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функция для вывода с цветом
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Проверка аргументов
if [ "$1" != "--dry-run" ] && [ "$1" != "--fix" ]; then
    echo "Использование: $0 --dry-run | --fix"
    echo "  --dry-run  - только анализ проблем"
    echo "  --fix      - анализ и исправление"
    exit 1
fi

MODE=$1
COMMAND="fix_unsupported_languages $MODE"

print_info "Проверка состояния Docker контейнеров..."

# Определение имен контейнеров (адаптируемся под разные конфигурации)
QUIZ_BACKEND_CONTAINER=$(docker ps --format "table {{.Names}}" | grep -E "(quiz_backend|quiz_backend_local_prod)" | head -1)
DB_CONTAINER=$(docker ps --format "table {{.Names}}" | grep -E "(quiz_db|postgres_db|postgres_db_local_prod)" | head -1)

# Проверка что контейнеры найдены
if [ -z "$QUIZ_BACKEND_CONTAINER" ]; then
    print_error "Контейнер quiz_backend не найден!"
    print_info "Доступные контейнеры:"
    docker ps --format "table {{.Names}}\t{{.Image}}"
    print_info "Запустите: docker-compose up -d"
    exit 1
fi

if [ -z "$DB_CONTAINER" ]; then
    print_error "Контейнер базы данных не найден!"
    print_info "Доступные контейнеры:"
    docker ps --format "table {{.Names}}\t{{.Image}}"
    print_info "Запустите: docker-compose up -d"
    exit 1
fi

print_success "Найдены контейнеры:"
print_info "  Backend: $QUIZ_BACKEND_CONTAINER"
print_info "  Database: $DB_CONTAINER"

print_success "Контейнеры работают"

# Резервное копирование если это исправление
if [ "$MODE" = "--fix" ]; then
    print_warning "Создание резервной копии базы данных..."
    BACKUP_FILE="backup_before_lang_fix_$(date +%Y%m%d_%H%M%S).sql"

    print_info "Создание бэкапа из контейнера: $DB_CONTAINER"
    if docker exec -i "$DB_CONTAINER" pg_dump -U postgres quiz_db > "$BACKUP_FILE"; then
        print_success "Резервная копия создана: $BACKUP_FILE"
        print_warning "Сохраните этот файл в безопасном месте!"
    else
        print_error "Не удалось создать резервную копию!"
        print_info "Возможные причины:"
        print_info "  - Неправильные учетные данные БД"
        print_info "  - База данных называется не 'quiz_db'"
        print_info "  - Нет доступа к контейнеру"
        read -p "Продолжить без бэкапа? (yes/no): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
fi

print_info "Запуск команды в контейнере: $QUIZ_BACKEND_CONTAINER"

# Запуск команды в контейнере
if [ "$MODE" = "--fix" ]; then
    # Для --fix режима используем автоматическое подтверждение
    print_info "Запуск в автоматическом режиме с подтверждением..."
    docker exec -i "$QUIZ_BACKEND_CONTAINER" bash -c "cd /app && echo 'yes' | python manage.py $COMMAND"
else
    # Для dry-run используем интерактивный режим
    print_info "Запуск в интерактивном режиме..."
    docker exec -it "$QUIZ_BACKEND_CONTAINER" bash -c "cd /app && python manage.py $COMMAND"
fi

if [ $? -eq 0 ]; then
    print_success "Команда выполнена успешно!"

    if [ "$MODE" = "--fix" ]; then
        print_info "Рекомендации после исправления:"
        echo "  - Проверьте работу сайта"
        echo "  - Очистите кэш если используется"
        echo "  - Проверьте логи за последние дни"
        echo "  - Убедитесь что Telegram опросы работают корректно"
    fi
else
    print_error "Ошибка выполнения команды!"
    exit 1
fi