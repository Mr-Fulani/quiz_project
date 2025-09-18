#!/bin/bash

export CURRENT_UID=$(id -u)
export CURRENT_GID=$(id -g)

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
docker compose -f docker-compose.local-prod.yml down --remove-orphans

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
    # Если сертификаты уже есть, сразу запускаем все с SSL
    docker compose -f docker-compose.local-prod.yml up -d --build
else
    echo "🚀 Запуск базовых сервисов (без SSL)..."
    # Запускаем только базовые сервисы без SSL
    docker compose -f docker-compose.local-prod.yml up -d database quiz_backend mini_app

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
    # Перезапускаем все сервисы с SSL сертификатами
    docker compose -f docker-compose.local-prod.yml down
    docker compose -f docker-compose.local-prod.yml up -d --build
fi

echo "✅ Продакшен запущен!"
