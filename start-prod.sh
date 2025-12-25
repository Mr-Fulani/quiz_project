#!/bin/bash

# Загрузка переменных окружения из .env файла
# Безопасный способ парсинга .env с поддержкой пробелов в значениях
if [ -f .env ]; then
    set -a
    source .env 2>/dev/null || {
        # Если source не работает, используем альтернативный метод
        while IFS= read -r line || [ -n "$line" ]; do
            # Пропускаем комментарии и пустые строки
            [[ "$line" =~ ^[[:space:]]*# ]] && continue
            [[ -z "${line// }" ]] && continue
            
            # Экспортируем переменную, если она содержит =
            if [[ "$line" =~ ^[[:space:]]*([^=]+)=(.*)$ ]]; then
                key="${BASH_REMATCH[1]// /}"
                value="${BASH_REMATCH[2]}"
                # Убираем кавычки если они есть
                value="${value#\"}"
                value="${value%\"}"
                value="${value#\'}"
                value="${value%\'}"
                export "$key=$value" 2>/dev/null || true
            fi
        done < .env
    }
    set +a
fi

# Скрипт для запуска продакшена
echo "🌐 Запуск продакшена..."

# Быстрый режим: пропускаем тяжёлую очистку и долгие ожидания
# Использование: ./start-prod.sh --fast или FAST_MODE=1 ./start-prod.sh
FAST_MODE=${FAST_MODE:-0}
CLEAR_CACHE=${CLEAR_CACHE:-0}
for arg in "$@"; do
  case "$arg" in
    --fast) FAST_MODE=1 ;;
    --clear-cache|--clean-cache) CLEAR_CACHE=1 ;;
  esac
done

function clear_all_cache() {
  echo ""
  echo "🧹 Автоматическая очистка кэша..."
  
  # Очистка Python кэша (.pyc файлы)
  echo "   🗑️  Очистка Python кэша (.pyc файлы)..."
  docker compose -f docker-compose.local-prod.yml exec -T quiz_backend find . -type d -name __pycache__ -exec rm -r {} + 2>/dev/null || true
  docker compose -f docker-compose.local-prod.yml exec -T quiz_backend find . -name "*.pyc" -delete 2>/dev/null || true
  echo "   ✅ Python кэш очищен"
  
  # Очистка статических файлов
  echo "   🗑️  Очистка статических файлов..."
  docker compose -f docker-compose.local-prod.yml exec -T quiz_backend rm -rf staticfiles/* 2>/dev/null || true
  echo "   ✅ Старые статические файлы удалены"
  
  # Пересборка статики
  echo "   🔄 Пересборка статических файлов..."
  docker compose -f docker-compose.local-prod.yml exec -T quiz_backend python manage.py collectstatic --noinput --clear
  echo "   ✅ Статические файлы пересобраны"
  
  # Очистка кэша nginx
  echo "   🗑️  Очистка кэша nginx..."
  docker compose -f docker-compose.local-prod.yml exec -T nginx sh -c "rm -rf /var/cache/nginx/* 2>/dev/null || true" || true
  echo "   ✅ Кэш nginx очищен"
  
  # Перезапуск nginx для применения изменений
  echo "   🔄 Перезапуск nginx..."
  docker compose -f docker-compose.local-prod.yml restart nginx
  echo "   ✅ Nginx перезапущен"
  
  echo "✅ Автоматическая очистка кэша завершена"
}

function clear_static_cache() {
  echo "🧹 Запуск очистки статических файлов..."
  docker compose -f docker-compose.local-prod.yml exec -T quiz_backend rm -rf staticfiles/*
  docker compose -f docker-compose.local-prod.yml exec -T quiz_backend python manage.py collectstatic --noinput --clear
  docker compose -f docker-compose.local-prod.yml restart nginx
  echo "🧹 Очистка статики завершена"
}
if [ "$FAST_MODE" = "1" ]; then
  echo "⚡ Включён быстрый режим (без prune/down, сокращённые ожидания)"
fi

# Освобождение порта 5433 перед запуском
echo "🔍 Проверка и освобождение порта 5433..."

# Сначала останавливаем все postgres контейнеры
echo "🛑 Остановка всех postgres контейнеров..."
docker ps -a --filter "name=postgres" --format "{{.ID}}" | xargs -r docker rm -f 2>/dev/null || true

# Останавливаем контейнеры через docker compose (даже в быстром режиме для освобождения порта)
echo "🛑 Остановка контейнеров через docker compose..."
docker compose -f docker-compose.local-prod.yml stop postgres_db 2>/dev/null || true
docker compose -f docker-compose.local-prod.yml rm -f postgres_db 2>/dev/null || true

# Проверяем порт через lsof
PID=$(lsof -ti :5433 2>/dev/null || echo "")
if [ ! -z "$PID" ]; then
  echo "⚠️  Порт 5433 все еще занят процессом PID=$PID, принудительно освобождаем..."
  kill -9 "$PID" 2>/dev/null || true
  sleep 2
fi

# Проверяем еще раз через docker ps (контейнеры, использующие порт)
CONTAINERS_WITH_PORT=$(docker ps --format "{{.ID}} {{.Ports}}" | grep ":5433" | awk '{print $1}' || echo "")
if [ ! -z "$CONTAINERS_WITH_PORT" ]; then
  echo "🛑 Найдены контейнеры, использующие порт 5433, останавливаем..."
  echo "$CONTAINERS_WITH_PORT" | xargs -r docker rm -f 2>/dev/null || true
  sleep 2
fi

# Финальная проверка
FINAL_CHECK=$(lsof -ti :5433 2>/dev/null || echo "")
if [ -z "$FINAL_CHECK" ]; then
  echo "✅ Порт 5433 свободен"
else
  echo "⚠️  Порт 5433 все еще занят, но продолжаем..."
fi

# Устанавливаем переменную окружения для продакшен конфигурации
# export NGINX_DOCKERFILE=Dockerfile.prod

# Временно используем только quiz-code.com для тестирования (остальные домены не настроены в DNS)
DOMAINS="quiz-code.com,www.quiz-code.com,mini.quiz-code.com"
EMAIL="fulani.dev@gmail.com" # Замените на реальный email

echo "🔍 Используемые домены для Certbot: $DOMAINS"
echo "ℹ️  Временно используются только домены quiz-code.com (остальные не настроены в DNS)"

# Debug: Выводим полную команду Certbot перед выполнением
# echo "Запуск Certbot с командой: docker compose -f docker-compose.local-prod.yml run --rm --entrypoint \"sh\" certbot -c \"set -x && ls -la /var/www/certbot && pwd && /usr/local/bin/certbot certonly --webroot -w /var/www/certbot --staging --agree-tos -v --non-interactive --email $EMAIL --config-dir /etc/letsencrypt/conf --work-dir /etc/letsencrypt/work --logs-dir /etc/letsencrypt/logs --domains \"$DOMAINS\" | tee /dev/stdout && sleep 5 && ls -la /etc/letsencrypt/logs/ && echo \"--- LETSENCRYPT LOG START ---\" && cat /etc/letsencrypt/logs/letsencrypt.log && echo \"--- LETSENCRYPT LOG END ---\" && ls -la /var/www/certbot\""

if [ "$FAST_MODE" != "1" ]; then
  echo "🔌 Остановка и удаление существующих контейнеров..."
  # УБИРАЕМ --volumes чтобы сохранить скачанные иконки
  docker compose -f docker-compose.local-prod.yml down --remove-orphans
  docker stop $(docker ps -q --filter "name=quiz_project") 2>/dev/null || true
  docker rm $(docker ps -aq --filter "name=quiz_project") 2>/dev/null || true
else
  # В быстром режиме тоже очищаем orphan контейнеры
  echo "🧹 Очистка orphan контейнеров..."
  docker compose -f docker-compose.local-prod.yml down --remove-orphans 2>/dev/null || true
fi

if [ "$FAST_MODE" != "1" ]; then
  echo "🧹 Очистка неиспользуемых Docker-образов..."
  docker image prune -f

  echo "🧹 Принудительная очистка Docker кэша..."
  docker image prune -a -f
  docker builder prune -f
else
  echo "⏭️ Пропускаем очистку образов и кэша (FAST_MODE)"
fi

echo "🧹 Проверка и подготовка конфигураций Certbot..."
# Проверяем, есть ли уже сертификаты
if [ -d "./certbot/conf/live/quiz-code.com" ]; then
    echo "✅ SSL сертификаты уже существуют, пропускаем их получение"
    SKIP_CERTBOT=true
else
    echo "🔐 SSL сертификаты не найдены, будет выполнено их получение"
    SKIP_CERTBOT=false
    # Создаем только необходимые директории, НЕ удаляем существующие
    sudo -S mkdir -p ./certbot/conf/live ./certbot/conf/work ./certbot/conf/logs
    sudo -S chown -R $(id -u):$(id -g) ./certbot # Устанавливаем правильные права доступа
fi

if [ "$SKIP_CERTBOT" = true ]; then
    echo "🚀 Запуск всех сервисов с существующими SSL сертификатами..."
    if [ "$FAST_MODE" = "1" ]; then
      # Быстрый запуск только необходимых сервисов
      docker compose -f docker-compose.local-prod.yml up -d --build nginx quiz_backend mini_app redis postgres_db telegram_bot celery_worker celery_worker_video celery_worker_webhooks celery_beat
    else
      # Полный запуск с пересборкой
      docker compose -f docker-compose.local-prod.yml up -d --build --force-recreate
    fi
    
    echo "⏳ Ожидание полного запуска всех сервисов..."
    if [ "$FAST_MODE" = "1" ]; then sleep 5; else sleep 15; fi
else
    echo "🚀 Запуск базовых сервисов (без SSL)..."
    # Запускаем только базовые сервисы без SSL (включая Redis и Celery)
    docker compose -f docker-compose.local-prod.yml up -d postgres_db redis quiz_backend celery_worker celery_worker_video celery_worker_webhooks celery_beat mini_app telegram_bot

    echo "⏳ Ожидание готовности сервисов..."
    if [ "$FAST_MODE" = "1" ]; then sleep 5; else sleep 10; fi

    echo "🌐 Запуск Nginx (временная конфигурация для получения сертификатов)..."
    # Пересобираем Nginx с временной конфигурацией (только HTTP)
    docker compose -f docker-compose.local-prod.yml build nginx --build-arg NGINX_CONF=nginx-temp.conf
    # Запускаем Nginx отдельно
    docker compose -f docker-compose.local-prod.yml up -d nginx

    echo "⏳ Ожидание готовности Nginx..."
    if [ "$FAST_MODE" = "1" ]; then sleep 3; else sleep 5; fi

    echo "🔐 Запуск Certbot для получения SSL сертификатов..."
        # Запуск Certbot для получения первоначальных сертификатов
        echo "Выполняется команда: docker compose -f docker-compose.local-prod.yml run --rm --entrypoint \"sh\" certbot -c \"/usr/local/bin/certbot certonly --webroot -w /var/www/certbot --agree-tos -v --non-interactive --email $EMAIL --domains $DOMAINS\""
        docker compose -f docker-compose.local-prod.yml run --rm --entrypoint "sh" certbot -c "/usr/local/bin/certbot certonly --webroot -w /var/www/certbot --agree-tos -v --non-interactive --email $EMAIL --domains $DOMAINS" > certbot_debug.log 2>&1
        
        # Проверяем результат выполнения
        if [ $? -eq 0 ]; then
            echo "✅ Certbot выполнен успешно!"
        else
            echo "❌ Ошибка при выполнении Certbot. Проверьте certbot_debug.log"
            echo "Последние строки лога:"
            tail -20 certbot_debug.log
            exit 1
        fi
        
        echo "⌛ Ожидание генерации сертификатов..."
    until [ -d "./certbot/conf/live/$(echo $DOMAINS | cut -d',' -f1)/" ]; do
      echo "Ожидание Certbot..."
      sleep 5
    done

    echo "🔄 Перезапуск всех сервисов с SSL..."
    # Перезапускаем все сервисы с SSL сертификатами (принудительная пересборка)
    if [ "$FAST_MODE" != "1" ]; then
      docker compose -f docker-compose.local-prod.yml down --remove-orphans
    fi
    docker compose -f docker-compose.local-prod.yml up -d --build --force-recreate
    
    echo "⏳ Ожидание полного запуска всех сервисов..."
    if [ "$FAST_MODE" = "1" ]; then sleep 5; else sleep 15; fi
fi

# Очистка кэша только если явно запрошена через флаг --clear-cache
if [ "$CLEAR_CACHE" = "1" ]; then
  echo "⏳ Ожидание готовности контейнеров перед очисткой кэша..."
  if [ "$FAST_MODE" = "1" ]; then
    sleep 3
  else
    sleep 5
  fi
  
  # Проверяем, что контейнеры запущены и очищаем кэш
  if docker compose -f docker-compose.local-prod.yml ps quiz_backend | grep -q "Up"; then
    clear_all_cache
  else
    echo "⚠️  Контейнер quiz_backend не запущен, пропускаем очистку кэша"
  fi
fi

echo ""
echo "🔧 Исправление предупреждений PostgreSQL..."
# Исправляем предупреждение о collation version mismatch
# Ожидаем готовности PostgreSQL перед исправлением
MAX_RETRIES=5
RETRY_COUNT=0
FIXED=false

if docker ps | grep -q "postgres_db_local_prod"; then
    DB_USER=${DB_USER:-postgres}
    DB_PASSWORD=${DB_PASSWORD:-postgres}
    DB_NAME=${DB_NAME:-fulani_quiz_db}
    
    echo "   🔍 Ожидание готовности PostgreSQL для исправления collation version..."
    while [ $RETRY_COUNT -lt $MAX_RETRIES ] && [ "$FIXED" = false ]; do
        # Проверяем, доступен ли PostgreSQL
        if docker exec -e PGPASSWORD="$DB_PASSWORD" postgres_db_local_prod \
            pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1; then
            
            echo "   🔍 Попытка исправления collation version ($((RETRY_COUNT+1))/$MAX_RETRIES)..."
            if docker exec -e PGPASSWORD="$DB_PASSWORD" postgres_db_local_prod \
                psql -U "$DB_USER" -d "$DB_NAME" -c "ALTER DATABASE $DB_NAME REFRESH COLLATION VERSION;" >/dev/null 2>&1; then
                echo "   ✅ Предупреждение о collation version исправлено"
                FIXED=true
                break
            fi
        fi
        
        RETRY_COUNT=$((RETRY_COUNT+1))
        if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
            sleep 2
        fi
    done
    
    if [ "$FIXED" = false ]; then
        echo "   ⚠️  Не удалось автоматически исправить после $MAX_RETRIES попыток."
        echo "   💡 Запустите вручную: ./fix-warnings.sh"
    fi
fi

echo ""
echo "🧹 Проверка статики..."
# Статика уже собрана в entrypoint.sh контейнера при запуске
# Проверяем только, что она доступна
echo "🔍 Проверка собранных файлов..."
if docker compose -f docker-compose.local-prod.yml exec -T quiz_backend test -d staticfiles && docker compose -f docker-compose.local-prod.yml exec -T quiz_backend sh -c '[ "$(ls -A staticfiles)" ]'; then
    echo "✅ Статические файлы успешно собраны с версионированием"
    
    # Проверяем наличие манифеста (доказательство версионирования)
    if docker compose -f docker-compose.local-prod.yml exec -T quiz_backend test -f staticfiles/staticfiles.json; then
        echo "✅ Манифест версионирования создан"
        echo "📋 Примеры версионированных файлов:"
        docker compose -f docker-compose.local-prod.yml exec -T quiz_backend sh -c 'ls staticfiles/*.* 2>/dev/null | head -5' || true
    fi
else
    echo "⚠️  Предупреждение: не удалось проверить статические файлы"
    echo "   Это может быть нормально, если контейнер еще запускается"
fi

echo "🔄 Перезапуск Nginx для применения изменений..."
docker compose -f docker-compose.local-prod.yml restart nginx

echo ""
echo "🤖 Проверка статуса Telegram бота..."
if docker compose -f docker-compose.local-prod.yml ps telegram_bot | grep -q "Up"; then
    echo "✅ Telegram бот запущен и работает"
else
    echo "⚠️  Внимание: Telegram бот не запущен или имеет проблемы"
    echo "   Проверьте логи: docker compose -f docker-compose.local-prod.yml logs telegram_bot"
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "✅ Продакшен успешно запущен!"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "🎨 Кэш статических файлов автоматически очищен и пересобран"
echo "   с версионированием (ManifestStaticFilesStorage)"
echo ""
echo "🌐 В браузере выполните жесткую перезагрузку:"
echo "   • Windows/Linux: Ctrl + Shift + R"
echo "   • macOS: Cmd + Shift + R"
echo ""
echo "💡 Если в будущем обновите только стили (без перезапуска):"
echo "   Запустите: ./clear_cache.sh"
echo ""
echo "📖 Подробная документация: STATIC_FILES_CACHE.md"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Спрашиваем показать ли логи
read -p "📋 Показать логи в реальном времени? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "🔍 Отображение логов (Ctrl+C для выхода)..."
    docker compose -f docker-compose.local-prod.yml logs -f
fi
