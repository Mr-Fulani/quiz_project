FROM nginx:1.21.6-alpine

# Копируем конфигурацию Nginx
COPY nginx.conf /etc/nginx/nginx.conf

# Создаем директории для сертификатов
RUN mkdir -p /etc/letsencrypt/live/quiz-code.com
RUN mkdir -p /etc/letsencrypt/live/quiz-format.com
RUN mkdir -p /etc/letsencrypt/live/quiz-game.co

# Создаем директории для mini поддоменов
RUN mkdir -p /etc/letsencrypt/live/mini.quiz-code.com
RUN mkdir -p /etc/letsencrypt/live/mini.quiz-format.com
RUN mkdir -p /etc/letsencrypt/live/mini.quiz-game.co

# Создаем директорию для веб-корня certbot
RUN mkdir -p /var/www/certbot

EXPOSE 80 443

CMD ["nginx", "-g", "daemon off;"]
