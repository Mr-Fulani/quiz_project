#!/bin/bash

# Скрипт для обновления SSL сертификатов Let's Encrypt
# Использование: ./renew-ssl.sh

echo "🔐 Обновление SSL сертификатов Let's Encrypt..."

# Определяем директорию проекта (скрипт может быть запущен из любой директории)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

# Проверяем, что мы в правильной директории
if [ ! -f "docker-compose.local-prod.yml" ]; then
    echo "❌ Ошибка: файл docker-compose.local-prod.yml не найден"
    echo "   Запустите скрипт из корневой директории проекта"
    exit 1
fi

# Проверяем, что контейнер certbot существует
if ! docker ps -a --format "{{.Names}}" | grep -q "certbot_local_prod"; then
    echo "⚠️  Контейнер certbot не найден. Запускаем сервисы..."
    docker compose -f docker-compose.local-prod.yml up -d certbot
    sleep 3
fi

# Обновляем сертификаты через certbot
echo "🔄 Запуск обновления сертификатов (dry-run)..."
docker compose -f docker-compose.local-prod.yml run --rm --entrypoint "" certbot sh -c "/usr/local/bin/certbot renew --dry-run"

# Проверяем результат dry-run
if [ $? -eq 0 ]; then
    echo "✅ Dry-run успешен. Выполняем реальное обновление..."
    docker compose -f docker-compose.local-prod.yml run --rm --entrypoint "" certbot sh -c "/usr/local/bin/certbot renew"
else
    echo "⚠️  Dry-run показал проблемы. Проверьте логи выше."
    exit 1
fi

# Проверяем результат обновления
if [ $? -eq 0 ]; then
    echo "✅ Сертификаты успешно обновлены!"
    
    # Перезагружаем nginx для применения новых сертификатов
    echo "🔄 Перезагрузка nginx для применения новых сертификатов..."
    docker compose -f docker-compose.local-prod.yml exec nginx nginx -s reload
    
    if [ $? -eq 0 ]; then
        echo "✅ Nginx успешно перезагружен"
    else
        echo "⚠️  Не удалось перезагрузить nginx через reload. Перезапускаем контейнер..."
        docker compose -f docker-compose.local-prod.yml restart nginx
    fi
    
    # Показываем информацию о новых сертификатах
    echo ""
    echo "📋 Информация о обновленных сертификатах:"
    if docker ps --format "{{.Names}}" | grep -q "certbot_local_prod"; then
        docker compose -f docker-compose.local-prod.yml exec certbot openssl x509 -in /etc/letsencrypt/live/quiz-code.com/fullchain.pem -noout -dates 2>/dev/null || \
        docker compose -f docker-compose.local-prod.yml run --rm --entrypoint "" certbot sh -c "openssl x509 -in /etc/letsencrypt/live/quiz-code.com/fullchain.pem -noout -dates"
    else
        docker compose -f docker-compose.local-prod.yml run --rm --entrypoint "" certbot sh -c "openssl x509 -in /etc/letsencrypt/live/quiz-code.com/fullchain.pem -noout -dates"
    fi
    
    echo ""
    echo "✅ Обновление SSL сертификатов завершено успешно!"
else
    echo "❌ Ошибка при обновлении сертификатов"
    echo "   Проверьте логи: docker compose -f docker-compose.local-prod.yml logs certbot"
    exit 1
fi

