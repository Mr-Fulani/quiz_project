# Dockerfile для nginx сервера
FROM nginx:alpine

ARG NGINX_CONF=nginx-local.conf
COPY ${NGINX_CONF} /etc/nginx/nginx.conf

# Создаем необходимые директории
RUN mkdir -p /var/www/certbot

# Открываем порты
EXPOSE 80 443 8080

# Запускаем nginx
CMD ["nginx", "-g", "daemon off;"]
