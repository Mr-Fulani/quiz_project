#!/bin/bash

export CURRENT_UID=$(id -u)
export CURRENT_GID=$(id -g)

# Скрипт для запуска продакшена
echo "🌐 Запуск продакшена..."

# Устанавливаем переменную окружения для продакшен конфигурации
# export NGINX_DOCKERFILE=Dockerfile.prod

# Извлекаем домены из nginx-prod.conf (для Certbot), учитывая многострочные определения
DOMAINS=$(awk '/server_name/{p=1; next} /;/{if(p){gsub(/;/,"",$0); print; p=0;}} p' nginx/nginx-prod.conf | xargs | tr ' ' ',' | sed 's/,$//')
EMAIL="fulani.dev@gmail.com" # Замените на реальный email

# Debug: Выводим полную команду Certbot перед выполнением
# echo "Запуск Certbot с командой: docker compose -f docker-compose.local-prod.yml run --rm --entrypoint \"sh\" certbot -c \"set -x && ls -la /var/www/certbot && pwd && /usr/local/bin/certbot certonly --webroot -w /var/www/certbot --staging --agree-tos -v --non-interactive --email $EMAIL --config-dir /etc/letsencrypt/conf --work-dir /etc/letsencrypt/work --logs-dir /etc/letsencrypt/logs --domains \"$DOMAINS\" | tee /dev/stdout && sleep 5 && ls -la /etc/letsencrypt/logs/ && echo \"--- LETSENCRYPT LOG START ---\" && cat /etc/letsencrypt/logs/letsencrypt.log && echo \"--- LETSENCRYPT LOG END ---\" && ls -la /var/www/certbot\""

echo "🔌 Остановка и удаление существующих контейнеров..."
docker compose down --volumes

echo "🧹 Очистка предыдущих конфигураций Certbot..."
sudo -S rm -rf ./certbot/conf
sudo -S mkdir -p ./certbot/conf/live ./certbot/conf/work ./certbot/conf/logs
sudo -S chown -R $(id -u):$(id -g) ./certbot # Устанавливаем правильные права доступа

echo "⏳ Запуск Certbot для получения первоначальных сертификатов..."
    # Запуск Certbot для получения первоначальных сертификатов
    docker compose run --rm --entrypoint "sh" certbot -c "set -x && ls -la /var/www/certbot && pwd && /usr/local/bin/certbot certonly --webroot -w /var/www/certbot \\
              --agree-tos \\
              -v \\
              --non-interactive \\
              --email $EMAIL \\
              --config-dir /etc/letsencrypt/conf \\
              --work-dir /etc/letsencrypt/work \\
              --logs-dir /etc/letsencrypt/logs \\
              --domains \"$DOMAINS\" | tee /dev/stdout && sleep 5 && ls -la /etc/letsencrypt/logs/ && echo \"--- LETSENCRYPT LOG START ---\" && cat /etc/letsencrypt/logs/letsencrypt.log && echo \"--- LETSENCRYPT LOG END ---\" && ls -la /var/www/certbot" > certbot_debug.log 2>&1
    
    echo "⌛ Ожидание генерации сертификатов..."
    # Certbot теперь запускается вручную после старта контейнера

    # Ожидание Certbot (этот шаг теперь будет выполнен после ручного запуска)
until [ -d "./certbot/conf/live/$(echo $DOMAINS | cut -d',' -f1)/" ]; do
  echo "Ожидание Certbot..."
  sleep 5
done

echo "✅ Сертификаты сгенерированы! Запуск всех служб..."
docker compose up -d --build

echo "✅ Продакшен запущен!"
