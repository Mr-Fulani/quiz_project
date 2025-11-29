# Команды для просмотра логов на продакшене

## 1. Просмотр логов Django контейнера (рекомендуется)

### Последние 100 строк
```bash
docker logs quiz_backend_local_prod --tail 100
```

### Последние 500 строк (для поиска запросов формы контакта)
```bash
docker logs quiz_backend_local_prod --tail 500
```

### Просмотр в реальном времени (follow)
```bash
docker logs quiz_backend_local_prod -f
```

### Просмотр с временными метками
```bash
docker logs quiz_backend_local_prod -f --timestamps
```

### Фильтрация по ключевому слову (например, "contact")
```bash
docker logs quiz_backend_local_prod --tail 500 | grep -i "contact"
```

### Фильтрация по времени (последние 10 минут)
```bash
docker logs quiz_backend_local_prod --since 10m
```

### Поиск ошибок email
```bash
docker logs quiz_backend_local_prod --tail 500 | grep -i "email\|mail\|smtp"
```

---

## 2. Просмотр логов Gunicorn из файлов

### Логи ошибок Gunicorn
```bash
docker exec quiz_backend_local_prod tail -f /app/logs/gunicorn-error.log
```

### Последние 100 строк логов ошибок
```bash
docker exec quiz_backend_local_prod tail -100 /app/logs/gunicorn-error.log
```

### Логи доступа Gunicorn
```bash
docker exec quiz_backend_local_prod tail -f /app/logs/gunicorn-access.log
```

### Поиск в логах ошибок
```bash
docker exec quiz_backend_local_prod grep -i "email\|contact" /app/logs/gunicorn-error.log | tail -20
```

---

## 3. Просмотр логов Django через docker-compose

Если используется docker-compose, можно использовать:

```bash
# Из директории проекта
cd /opt/quiz_project/quiz_project

# Просмотр логов всех сервисов
docker-compose -f docker-compose.local-prod.yml logs quiz_backend

# Просмотр в реальном времени
docker-compose -f docker-compose.local-prod.yml logs -f quiz_backend

# Последние 500 строк
docker-compose -f docker-compose.local-prod.yml logs --tail 500 quiz_backend

# С временными метками
docker-compose -f docker-compose.local-prod.yml logs -f --timestamps quiz_backend
```

---

## 4. Поиск конкретного запроса формы контакта

### Поиск POST запроса на /contact/submit/
```bash
docker logs quiz_backend_local_prod --tail 1000 | grep -A 20 "POST.*contact/submit"
```

### Поиск всех сообщений о форме контакта
```bash
docker logs quiz_backend_local_prod --tail 1000 | grep -B 5 -A 30 "Получен POST-запрос на /contact/submit/"
```

### Поиск ошибок отправки email
```bash
docker logs quiz_backend_local_prod --tail 1000 | grep -B 5 -A 10 "Ошибка отправки email"
```

### Поиск успешной отправки
```bash
docker logs quiz_backend_local_prod --tail 1000 | grep -B 5 -A 5 "Письмо успешно отправлено"
```

---

## 5. Проверка логов после отправки формы

```bash
# 1. Сначала запустите просмотр логов в реальном времени
docker logs quiz_backend_local_prod -f --timestamps

# 2. Затем отправьте форму контакта в браузере

# 3. В логах вы должны увидеть:
# - "Получен POST-запрос на /contact/submit/"
# - "Форма прошла валидацию"
# - "Обработка сообщения от ..."
# - Настройки EMAIL_HOST, EMAIL_PORT и т.д.
# - Результат отправки письма или ошибку
```

---

## 6. Экспорт логов в файл для анализа

```bash
# Экспорт последних 1000 строк
docker logs quiz_backend_local_prod --tail 1000 > /tmp/django_logs.txt

# Экспорт с фильтром по email
docker logs quiz_backend_local_prod --tail 1000 | grep -i "email\|contact" > /tmp/email_logs.txt

# Просмотр экспортированного файла
cat /tmp/email_logs.txt
```

---

## 7. Мониторинг логов в реальном времени с фильтрацией

```bash
# Смотреть только логи, связанные с контактом и email
docker logs quiz_backend_local_prod -f | grep --line-buffered -i "contact\|email\|mail\|smtp\|fulani.dev@gmail.com"
```

---

## 8. Проверка всех контейнеров одновременно

```bash
# Логи всех контейнеров
docker-compose -f docker-compose.local-prod.yml logs -f

# Только Django и Nginx (для web запросов)
docker-compose -f docker-compose.local-prod.yml logs -f quiz_backend nginx_local_prod
```

---

## Быстрая команда для диагностики проблемы с email

Выполните эту команду для просмотра всех релевантных логов:

```bash
docker logs quiz_backend_local_prod --tail 500 --timestamps | grep -B 3 -A 15 -i "contact\|email\|mail\|smtp\|POST.*submit"
```

---

## Полезные команды для проверки переменных окружения

```bash
# Проверить email настройки внутри контейнера
docker exec quiz_backend_local_prod env | grep EMAIL

# Проверить настройки Django
docker exec -it quiz_backend_local_prod python manage.py shell -c "
from django.conf import settings
print(f'EMAIL_HOST: {settings.EMAIL_HOST}')
print(f'EMAIL_PORT: {settings.EMAIL_PORT}')
print(f'EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}')
print(f'EMAIL_USE_SSL: {settings.EMAIL_USE_SSL}')
print(f'EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}')
print(f'DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}')
print(f'EMAIL_ADMIN: {settings.EMAIL_ADMIN}')
"
```

