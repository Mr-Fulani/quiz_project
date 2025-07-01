# Используем официальный образ Nginx
FROM nginx:1.21.6-alpine

# Удаляем стандартную конфигурацию Nginx
RUN rm /etc/nginx/conf.d/default.conf

# Копируем наш кастомный файл конфигурации
COPY nginx.conf /etc/nginx/nginx.conf 