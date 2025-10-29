#!/bin/bash

# Скрипт для запуска продакшена
echo "🌐 Запуск продакшена..."

# Устанавливаем переменную окружения для продакшен конфигурации
# export NGINX_DOCKERFILE=Dockerfile.prod

# Временно используем только quiz-code.com для тестирования (остальные домены не настроены в DNS)
DOMAINS="quiz-code.com,www.quiz-code.com,mini.quiz-code.com"
EMAIL="fulani.dev@gmail.com" # Замените на реальный email

echo "🔍 Используемые домены для Certbot: $DOMAINS"
echo "ℹ️  Временно используются только домены quiz-code.com (остальные не настроены в DNS)"

# Debug: Выводим полную команду Certbot перед выполнением
# echo "Запуск Certbot с командой: docker compose -f docker-compose.local-prod.yml run --rm --entrypoint \"sh\" certbot -c \"set -x && ls -la /var/www/certbot && pwd && /usr/local/bin/certbot certonly --webroot -w /var/www/certbot --staging --agree-tos -v --non-interactive --email $EMAIL --config-dir /etc/letsencrypt/conf --work-dir /etc/letsencrypt/work --logs-dir /etc/letsencrypt/logs --domains \"$DOMAINS\" | tee /dev/stdout && sleep 5 && ls -la /etc/letsencrypt/logs/ && echo \"--- LETSENCRYPT LOG START ---\" && cat /etc/letsencrypt/logs/letsencrypt.log && echo \"--- LETSENCRYPT LOG END ---\" && ls -la /var/www/certbot\""

echo "🔌 Остановка и удаление существующих контейнеров..."
# Принудительно останавливаем все контейнеры проекта
docker compose -f docker-compose.local-prod.yml down --volumes --remove-orphans
# Дополнительная очистка на случай конфликтов портов
docker stop $(docker ps -q --filter "name=quiz_project") 2>/dev/null || true
docker rm $(docker ps -aq --filter "name=quiz_project") 2>/dev/null || true

echo "🧹 Очистка неиспользуемых Docker-образов..."
docker image prune -f

echo "🧹 Принудительная очистка Docker кэша..."
# Удаляем все неиспользуемые образы (включая промежуточные)
docker image prune -a -f
# Очищаем кэш сборки
docker builder prune -f

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
    # Если сертификаты уже есть, сразу запускаем все с SSL (принудительная пересборка)
    docker compose -f docker-compose.local-prod.yml up -d --build --force-recreate
    
    echo "⏳ Ожидание полного запуска всех сервисов..."
    sleep 15
else
    echo "🚀 Запуск базовых сервисов (без SSL)..."
    # Запускаем только базовые сервисы без SSL (включая Redis и Celery)
    docker compose -f docker-compose.local-prod.yml up -d postgres_db redis quiz_backend celery_worker celery_beat mini_app

    echo "⏳ Ожидание готовности сервисов..."
    sleep 10

    echo "🌐 Запуск Nginx (временная конфигурация для получения сертификатов)..."
    # Пересобираем Nginx с временной конфигурацией (только HTTP)
    docker compose -f docker-compose.local-prod.yml build nginx --build-arg NGINX_CONF=nginx-temp.conf
    # Запускаем Nginx отдельно
    docker compose -f docker-compose.local-prod.yml up -d nginx

    echo "⏳ Ожидание готовности Nginx..."
    sleep 5

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
    docker compose -f docker-compose.local-prod.yml down
    docker compose -f docker-compose.local-prod.yml up -d --build --force-recreate
    
    echo "⏳ Ожидание полного запуска всех сервисов..."
    sleep 15
fi

echo ""
echo "🧹 Автоматическая очистка и пересборка кэша статических файлов..."
echo "📁 Очистка staticfiles в контейнере..."
docker compose -f docker-compose.local-prod.yml exec -T quiz_backend rm -rf staticfiles/* || true

echo "📦 Пересборка статических файлов с версионированием..."
docker compose -f docker-compose.local-prod.yml exec -T quiz_backend python manage.py collectstatic --noinput --clear

# Проверяем, что статика собралась корректно
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
fi

echo "🔄 Перезапуск Nginx для применения изменений..."
docker compose -f docker-compose.local-prod.yml restart nginx

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
