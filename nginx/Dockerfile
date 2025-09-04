# Dockerfile для nginx сервера
FROM nginx:alpine

# Копируем конфигурацию nginx (по умолчанию локальная)
COPY nginx-local.conf /etc/nginx/nginx.conf

# Создаем необходимые директории
RUN mkdir -p /var/www/certbot

# Открываем порты
EXPOSE 80 443 8080

# Запускаем nginx
CMD ["nginx", "-g", "daemon off;"]
