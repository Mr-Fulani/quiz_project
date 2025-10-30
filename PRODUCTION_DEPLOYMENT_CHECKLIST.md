# ✅ Чеклист деплоя в продакшн

## 📋 Перед деплоем

### 1. Проверка кода
- [ ] Все изменения закоммичены в Git
- [ ] Запушены в удаленный репозиторий
- [ ] Нет критических ошибок в логах разработки
- [ ] Все тесты проходят успешно

### 2. Проверка настроек (.env)
```bash
# Критические переменные для продакшена:
- [ ] DEBUG=False
- [ ] SECRET_KEY (уникальный, минимум 50 символов)
- [ ] ALLOWED_HOSTS (список доменов)
- [ ] DB_NAME, DB_USER, DB_PASSWORD (PostgreSQL)
- [ ] REDIS_URL=redis://redis_cache_prod:6379/1
- [ ] CELERY_BROKER_URL=redis://redis_cache_prod:6379/0
- [ ] EMAIL_HOST, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD
- [ ] STRIPE_SECRET_KEY, STRIPE_PUBLISHABLE_KEY (production keys)
```

### 3. Проверка файлов конфигурации
- [ ] `docker-compose.local-prod.yml` содержит Redis и Celery
- [ ] `start-prod.sh` обновлен и исполняемый (`chmod +x start-prod.sh`)
- [ ] `nginx/nginx-prod.conf` настроен правильно
- [ ] SSL сертификаты готовы или будут получены автоматически

---

## 🚀 Процесс деплоя

### Шаг 1: Подготовка сервера

```bash
# 1. Подключиться к серверу
ssh user@your-server.com

# 2. Перейти в директорию проекта
cd /path/to/quiz_project

# 3. Получить последние изменения
git pull origin main

# 4. Проверить статус
git status
```

### Шаг 2: Обновление зависимостей

```bash
# Проверить, что новые зависимости добавлены
cat quiz_backend/requirements.txt | grep -E "celery|redis|django-redis|django-celery-beat"

# Должны быть:
# celery==5.3.4
# redis==5.0.1
# django-redis==5.4.0
# django-celery-beat==2.5.0
```

### Шаг 3: Остановка старых контейнеров

```bash
# Остановить и удалить старые контейнеры
docker compose -f docker-compose.local-prod.yml down

# Опционально: очистить неиспользуемые образы
docker image prune -f
```

### Шаг 4: Запуск продакшена

```bash
# Использовать скрипт (рекомендуется)
./start-prod.sh

# Скрипт автоматически:
# - Останавливает старые контейнеры
# - Пересобирает образы
# - Запускает Redis, PostgreSQL, Django, Celery, Nginx
# - Получает SSL сертификаты (если нужно)
# - Собирает статику
```

### Шаг 5: Проверка сервисов

```bash
# Проверить статус всех контейнеров
docker compose -f docker-compose.local-prod.yml ps

# Должны работать:
# ✅ postgres_db_local_prod
# ✅ redis_cache_prod
# ✅ quiz_backend_local_prod
# ✅ celery_worker_prod
# ✅ celery_beat_prod
# ✅ mini_app_local_prod
# ✅ nginx_local_prod
# ✅ upbeat_robinson (telegram bot)
```

### Шаг 6: Проверка логов

```bash
# Django
docker compose -f docker-compose.local-prod.yml logs -f quiz_backend | tail -50

# Redis
docker compose -f docker-compose.local-prod.yml logs redis_cache_prod | tail -20

# Celery Worker
docker compose -f docker-compose.local-prod.yml logs -f celery_worker_prod | tail -30

# Celery Beat
docker compose -f docker-compose.local-prod.yml logs -f celery_beat_prod | tail -20

# Не должно быть критических ошибок (ERROR, CRITICAL)
```

### Шаг 7: Тестирование функциональности

```bash
# 1. Тест кэша
docker compose -f docker-compose.local-prod.yml run quiz_backend python manage.py cache_monitor --test

# Ожидаемый результат:
# ✅ Кэш работает корректно
# 📊 Hit Rate: >70%
# ⚡ Производительность: запись/чтение < 1s для 1000 операций

# 2. Тест Celery
docker compose -f docker-compose.local-prod.yml exec celery_worker_prod celery -A config inspect active

# Ожидаемый результат:
# -> celery@hostname: OK (активные задачи или пусто)

# 3. Тест подключения к Redis
docker compose -f docker-compose.local-prod.yml exec redis_cache_prod redis-cli ping

# Ожидаемый результат:
# PONG
```

### Шаг 8: Проверка сайта

```bash
# 1. Проверить доступность
curl -I https://quiz-code.com

# Ожидаемый результат:
# HTTP/2 200
# content-type: text/html

# 2. Проверить API
curl https://quiz-code.com/api/health/

# 3. Открыть в браузере
# https://quiz-code.com
```

### Шаг 9: Мониторинг первые 30 минут

```bash
# Следить за логами в реальном времени
docker compose -f docker-compose.local-prod.yml logs -f quiz_backend celery_worker_prod

# Обратить внимание на:
# - ❌ Ошибки подключения к Redis
# - ❌ Ошибки подключения к PostgreSQL
# - ❌ Медленные запросы (> 1 сек)
# - ❌ Необработанные исключения
```

---

## 🔍 Проверка метрик производительности

### 1. Время ответа сервера

```bash
# Должно быть < 200ms для главной страницы
curl -o /dev/null -s -w "Time: %{time_total}s\n" https://quiz-code.com/
```

### 2. Статистика Redis

```bash
docker compose -f docker-compose.local-prod.yml run quiz_backend python manage.py cache_monitor --stats

# Проверить:
# - Hit Rate > 70% ✅
# - Используемая память < 512MB ✅
# - Connected clients > 0 ✅
```

### 3. Статистика Gunicorn

```bash
# Проверить логи Gunicorn
docker compose -f docker-compose.local-prod.yml exec quiz_backend cat /app/logs/gunicorn-access.log | tail -20

# Должны быть записи о запросах:
# "GET /api/... HTTP/1.1" 200 - 0.123
```

### 4. Celery задачи

```bash
# Проверить выполненные задачи
docker compose -f docker-compose.local-prod.yml exec celery_worker_prod celery -A config inspect stats

# Проверить:
# - total: количество выполненных задач
# - Failed: 0 или минимум ошибок
```

---

## ⚠️ Troubleshooting

### Проблема: Redis не запускается

```bash
# Проверить логи
docker compose -f docker-compose.local-prod.yml logs redis_cache_prod

# Решение 1: Перезапустить
docker compose -f docker-compose.local-prod.yml restart redis_cache_prod

# Решение 2: Пересоздать контейнер
docker compose -f docker-compose.local-prod.yml up -d --force-recreate redis_cache_prod
```

### Проблема: Celery не обрабатывает задачи

```bash
# Проверить broker
docker compose -f docker-compose.local-prod.yml exec celery_worker_prod celery -A config inspect ping

# Проверить очередь задач
docker compose -f docker-compose.local-prod.yml exec redis_cache_prod redis-cli LLEN celery

# Перезапустить worker
docker compose -f docker-compose.local-prod.yml restart celery_worker_prod celery_beat_prod
```

### Проблема: Медленная работа сайта

```bash
# 1. Проверить количество SQL запросов
# В логах искать: "МНОГО SQL ЗАПРОСОВ"

# 2. Проверить hit rate кэша
docker compose -f docker-compose.local-prod.yml run quiz_backend python manage.py cache_monitor --stats

# 3. Очистить и прогреть кэш
docker compose -f docker-compose.local-prod.yml run quiz_backend python manage.py cache_monitor --clear

# 4. Увеличить количество Gunicorn workers (если много CPU)
# В .env: GUNICORN_WORKERS=8
```

### Проблема: Статика не загружается

```bash
# Пересобрать статику
docker compose -f docker-compose.local-prod.yml exec quiz_backend python manage.py collectstatic --noinput --clear

# Перезапустить nginx
docker compose -f docker-compose.local-prod.yml restart nginx_local_prod

# Проверить права доступа
docker compose -f docker-compose.local-prod.yml exec quiz_backend ls -la /app/staticfiles/
```

---

## 📊 Post-Deploy мониторинг

### День 1-3: Интенсивный мониторинг

```bash
# Каждый час проверять:
1. Логи на ошибки
2. Использование памяти (docker stats)
3. Hit rate кэша
4. Время ответа сервера
```

### Неделя 1: Регулярный мониторинг

```bash
# Каждый день:
1. Проверять логи ошибок
2. Анализировать медленные запросы
3. Проверять статистику Celery
```

### Команды для мониторинга

```bash
# Использование ресурсов
docker stats

# Топ процессов в контейнере
docker compose -f docker-compose.local-prod.yml exec quiz_backend top

# Размер базы данных
docker compose -f docker-compose.local-prod.yml exec postgres_db psql -U postgres -d fulani_quiz_db -c "SELECT pg_size_pretty(pg_database_size('fulani_quiz_db'));"

# Количество подключений к Redis
docker compose -f docker-compose.local-prod.yml exec redis_cache_prod redis-cli info clients
```

---

## 🎯 Критерии успешного деплоя

- [x] Все контейнеры работают (status: Up)
- [x] Сайт доступен по HTTPS
- [x] Redis работает, hit rate > 70%
- [x] Celery обрабатывает задачи
- [x] Время ответа < 200ms
- [x] Нет критических ошибок в логах
- [x] Email отправляется асинхронно
- [x] Статика и медиа загружаются
- [x] SSL сертификаты валидны

---

## 📞 Контакты для экстренной поддержки

- **Логи ошибок:** `/app/logs/django_errors.log`
- **Логи Gunicorn:** `/app/logs/gunicorn-error.log`
- **Документация:** `PRODUCTION_SETUP.md`, `DJANGO_CELERY_README.md`

**В случае критической проблемы:**
1. Откатиться на предыдущую версию: `git checkout <previous_commit>`
2. Перезапустить: `./start-prod.sh`
3. Проанализировать логи после стабилизации

