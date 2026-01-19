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

# Функция обработки ошибки бэкапа
handle_backup_error() {
    print_warning "Для ручного создания бэкапа выполните:"
    print_info "  docker exec -i $DB_CONTAINER pg_dump -U <user> <db_name> > backup.sql"
    print_info ""
    print_warning "ИЛИ пропустите бэкап и продолжите исправление"
    echo
    read -p "Продолжить без бэкапа? (yes/no): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
}

# Резервное копирование если это исправление
if [ "$MODE" = "--fix" ]; then
    print_warning "Создание резервной копии базы данных..."

    print_info "=== ДИАГНОСТИКА ПОДКЛЮЧЕНИЯ К БД ==="

    # Сначала проверим переменные окружения
    print_info "Проверка переменных окружения:"
    if [ -z "$DB_USER" ]; then
        print_warning "DB_USER не установлена, используем значение по умолчанию: postgres"
        DB_USER="postgres"
    else
        print_info "DB_USER=$DB_USER"
    fi

    if [ -z "$DB_PASSWORD" ]; then
        print_warning "DB_PASSWORD не установлена, используем значение по умолчанию: postgres"
        DB_PASSWORD="postgres"
    else
        print_info "DB_PASSWORD=[СКРЫТО]"
    fi

    if [ -z "$DB_NAME" ]; then
        print_warning "DB_NAME не установлена, используем значение по умолчанию: fulani_quiz_db"
        DB_NAME="fulani_quiz_db"
    else
        print_info "DB_NAME=$DB_NAME"
    fi

    BACKUP_FILE="backup_before_lang_fix_$(date +%Y%m%d_%H%M%S).sql"

    print_info "=== ПРОВЕРКА ДОСТУПА К КОНТЕЙНЕРУ ==="
    print_info "Контейнер БД: $DB_CONTAINER"

    # Проверяем что контейнер отвечает
    if ! docker exec "$DB_CONTAINER" echo "Контейнер доступен" >/dev/null 2>&1; then
        print_error "Контейнер $DB_CONTAINER недоступен!"
        handle_backup_error
        return
    fi
    print_success "Контейнер доступен"

    print_info "=== ПОПЫТКА ПОДКЛЮЧЕНИЯ К БД ==="
    print_info "Тестируем подключение с учетными данными:"
    print_info "  Host: localhost (внутри контейнера)"
    print_info "  Port: 5432"
    print_info "  User: $DB_USER"
    print_info "  Database: $DB_NAME"

    # Попытка 1: Прямое подключение без пароля (для отладки)
    print_info "Попытка 1: Проверка без пароля..."
    if docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT version();" 2>/dev/null | grep -q "PostgreSQL"; then
        print_success "Подключение без пароля работает!"
        BACKUP_CMD="docker exec -i \"$DB_CONTAINER\" pg_dump -U \"$DB_USER\" \"$DB_NAME\""
    else
        print_warning "Подключение без пароля не работает, пробуем с паролем..."

        # Попытка 2: Подключение с паролем через PGPASSWORD
        print_info "Попытка 2: Проверка с паролем..."
        if PGPASSWORD="$DB_PASSWORD" docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT version();" 2>/dev/null | grep -q "PostgreSQL"; then
            print_success "Подключение с паролем работает!"
            BACKUP_CMD="PGPASSWORD=\"$DB_PASSWORD\" docker exec -i \"$DB_CONTAINER\" pg_dump -U \"$DB_USER\" \"$DB_NAME\""
        else
            print_error "Подключение с паролем тоже не работает!"

            print_info "=== ДИАГНОСТИКА ПРОБЛЕМЫ ==="

            # Попытка 3: Проверить список баз данных без пароля
            print_info "Попытка 3: Проверка списка баз данных без пароля..."
            if docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -l 2>/dev/null | grep -q "$DB_NAME"; then
                print_info "База данных $DB_NAME существует (доступ без пароля)"
                print_info "Попробуйте: export DB_PASSWORD=''"
            else
                # Попытка 4: Проверить список баз данных с паролем
                print_info "Попытка 4: Проверка списка баз данных с паролем..."
                if PGPASSWORD="$DB_PASSWORD" docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -l 2>/dev/null | grep -q "$DB_NAME"; then
                    print_info "База данных $DB_NAME существует (доступ с паролем)"
                else
                    print_error "База данных $DB_NAME не найдена!"

                    # Попытка 5: Показать все доступные базы данных
                    print_info "Попытка 5: Список ВСЕХ доступных баз данных..."
                    echo "Без пароля:"
                    if docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -l 2>/dev/null | head -20; then
                        echo ""
                    fi
                    echo "С паролем:"
                    if PGPASSWORD="$DB_PASSWORD" docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -l 2>/dev/null | head -20; then
                        echo ""
                    fi
                fi
            fi

            # Попытка 6: Проверить подключение к стандартным базам
            print_info "Попытка 6: Тест подключения к стандартным базам..."
            for test_db in postgres template1 template0; do
                if PGPASSWORD="$DB_PASSWORD" docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$test_db" -c "SELECT 1;" >/dev/null 2>&1; then
                    print_success "Подключение к $test_db работает!"
                    print_info "Попробуйте: export DB_NAME=$test_db"
                    break
                fi
            done

            # Попытка 7: Проверить суперпользователя
            print_info "Попытка 7: Проверка суперпользователя postgres..."
            for test_user in postgres admin root; do
                if docker exec -i "$DB_CONTAINER" psql -U "$test_user" -d postgres -c "SELECT 1;" >/dev/null 2>&1; then
                    print_success "Найден пользователь $test_user без пароля!"
                    print_info "Попробуйте: export DB_USER=$test_user"
                    print_info "Попробуйте: export DB_PASSWORD=''"
                    break
                elif PGPASSWORD="postgres" docker exec -i "$DB_CONTAINER" psql -U "$test_user" -d postgres -c "SELECT 1;" >/dev/null 2>&1; then
                    print_success "Найден пользователь $test_user с паролем 'postgres'!"
                    print_info "Попробуйте: export DB_USER=$test_user"
                    print_info "Попробуйте: export DB_PASSWORD=postgres"
                    break
                fi
            done

            print_error "=== РЕКОМЕНДАЦИИ ==="
            print_info "1. Проверьте переменные окружения:"
            echo "   env | grep DB_"
            print_info "2. Проверьте учетные данные в docker-compose.yml"
            print_info "3. Попробуйте подключиться вручную:"
            echo "   docker exec -it $DB_CONTAINER psql -U postgres -d postgres"
            print_info "4. Проверьте логи контейнера:"
            echo "   docker logs $DB_CONTAINER"

            handle_backup_error
            return
        fi
    fi

    # Если дошли до сюда - подключение работает, создаем бэкап
    print_info "=== СОЗДАНИЕ РЕЗЕРВНОЙ КОПИИ ==="
    print_info "Команда бэкапа: $BACKUP_CMD > $BACKUP_FILE"

    if eval "$BACKUP_CMD" > "$BACKUP_FILE"; then
        BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
        print_success "Резервная копия создана: $BACKUP_FILE (размер: $BACKUP_SIZE)"
        print_warning "Сохраните этот файл в безопасном месте!"
        print_info "Для восстановления: psql -U $DB_USER -d $DB_NAME < $BACKUP_FILE"
    else
        print_error "Не удалось создать резервную копию!"
        handle_backup_error
        return
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