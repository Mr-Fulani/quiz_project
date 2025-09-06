#!/bin/bash

# Скрипт для запуска продакшена
echo "🌐 Запуск продакшена..."

# Устанавливаем переменную окружения для продакшен конфигурации
export NGINX_DOCKERFILE=Dockerfile.prod

# Определяем домены из nginx-prod.conf (для Certbot)
DOMAINS=$(grep -E 'server_name\s+' nginx/nginx-prod.conf | awk '{for(i=2;i<=NF;i++) print $i}' | tr -d ";" | tr -s ' ' ',' | sed 's/,$//g')
EMAIL="fulani.dev@gmail.com" # Замените на реальный email

echo "🔌 Остановка и удаление существующих контейнеров..."
docker compose down

echo "⏳ Запуск Certbot для получения первоначальных сертификатов..."
docker compose run --rm --entrypoint "\
  certbot certonly --webroot -w /var/www/certbot \
    --staging \
    --agree-tos \
    --non-interactive \
    --email $EMAIL \
    -d $(echo $DOMAINS | tr ',' ' -d ')"
certbot

echo "⌛ Ожидание генерации сертификатов..."
until [ -f "./certbot/conf/live/$(echo $DOMAINS | cut -d',' -f1)/fullchain.pem" ]; do
  echo "Ожидание Certbot..."
  sleep 5
done

echo "✅ Сертификаты сгенерированы! Запуск всех служб..."
docker compose up -d --build

echo "✅ Продакшен запущен!"
