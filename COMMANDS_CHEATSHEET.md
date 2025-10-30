# 🎯 Шпаргалка команд

## 📦 Docker Compose

### Локальная разработка (DEBUG=True)
```bash
# Запустить
docker compose up -d

# Остановить
docker compose down

# Перезапустить
docker compose restart

# Логи
docker compose logs -f

# Статус
docker compose ps
```

### Продакшн (DEBUG=False)
```bash
# Запустить
./start-prod.sh
# или
docker compose -f docker-compose.local-prod.yml up -d --build

# Остановить
docker compose -f docker-compose.local-prod.yml down

# Перезапустить
docker compose -f docker-compose.local-prod.yml restart

# Логи
docker compose -f docker-compose.local-prod.yml logs -f

# Статус
docker compose -f docker-compose.local-prod.yml ps
```

---

## 🔍 Мониторинг кэша

```bash
# Разработка
docker compose run web python manage.py cache_monitor
docker compose run web python manage.py cache_monitor --stats
docker compose run web python manage.py cache_monitor --clear
docker compose run web python manage.py cache_monitor --test

# Продакшн
docker compose -f docker-compose.local-prod.yml run quiz_backend python manage.py cache_monitor
docker compose -f docker-compose.local-prod.yml run quiz_backend python manage.py cache_monitor --stats
docker compose -f docker-compose.local-prod.yml run quiz_backend python manage.py cache_monitor --clear
docker compose -f docker-compose.local-prod.yml run quiz_backend python manage.py cache_monitor --test
```

---

## 🔄 Celery

### Разработка
```bash
# Проверить активные задачи
docker compose exec celery_worker celery -A config inspect active

# Проверить зарегистрированные задачи
docker compose exec celery_worker celery -A config inspect registered

# Статистика
docker compose exec celery_worker celery -A config inspect stats

# Проверить ping
docker compose exec celery_worker celery -A config inspect ping
```

### Продакшн
```bash
docker compose -f docker-compose.local-prod.yml exec celery_worker_prod celery -A config inspect active
docker compose -f docker-compose.local-prod.yml exec celery_worker_prod celery -A config inspect registered
docker compose -f docker-compose.local-prod.yml exec celery_worker_prod celery -A config inspect stats
docker compose -f docker-compose.local-prod.yml exec celery_worker_prod celery -A config inspect ping
```

---

## 💾 Redis

### Разработка
```bash
# Проверить подключение
docker compose exec redis redis-cli ping

# Проверить количество ключей
docker compose exec redis redis-cli DBSIZE

# Очистить всю БД (осторожно!)
docker compose exec redis redis-cli FLUSHDB

# Получить информацию
docker compose exec redis redis-cli INFO
```

### Продакшн
```bash
docker compose -f docker-compose.local-prod.yml exec redis_cache_prod redis-cli ping
docker compose -f docker-compose.local-prod.yml exec redis_cache_prod redis-cli DBSIZE
docker compose -f docker-compose.local-prod.yml exec redis_cache_prod redis-cli INFO
```

---

## 🗃️ PostgreSQL

### Разработка
```bash
# Подключиться к БД
docker compose exec database psql -U postgres -d fulani_quiz_db

# Список таблиц
docker compose exec database psql -U postgres -d fulani_quiz_db -c "\dt"

# Размер БД
docker compose exec database psql -U postgres -d fulani_quiz_db -c "SELECT pg_size_pretty(pg_database_size('fulani_quiz_db'));"

# Количество подключений
docker compose exec database psql -U postgres -d fulani_quiz_db -c "SELECT count(*) FROM pg_stat_activity;"
```

### Продакшн
```bash
docker compose -f docker-compose.local-prod.yml exec postgres_db psql -U postgres -d fulani_quiz_db
docker compose -f docker-compose.local-prod.yml exec postgres_db psql -U postgres -d fulani_quiz_db -c "\dt"
docker compose -f docker-compose.local-prod.yml exec postgres_db psql -U postgres -d fulani_quiz_db -c "SELECT pg_size_pretty(pg_database_size('fulani_quiz_db'));"
```

---

## 🐍 Django Management

### Разработка
```bash
# Любая Django команда
docker compose run web python manage.py <command>

# Миграции
docker compose run web python manage.py migrate

# Создать суперпользователя
docker compose run web python manage.py createsuperuser

# Собрать статику
docker compose run web python manage.py collectstatic --noinput

# Зайти в shell
docker compose run web python manage.py shell
```

### Продакшн
```bash
docker compose -f docker-compose.local-prod.yml run quiz_backend python manage.py <command>
docker compose -f docker-compose.local-prod.yml run quiz_backend python manage.py migrate
docker compose -f docker-compose.local-prod.yml run quiz_backend python manage.py createsuperuser
docker compose -f docker-compose.local-prod.yml run quiz_backend python manage.py collectstatic --noinput
docker compose -f docker-compose.local-prod.yml run quiz_backend python manage.py shell
```

---

## 🔧 Отладка

### Логи конкретного сервиса
```bash
# Разработка
docker compose logs -f quiz_backend
docker compose logs -f redis
docker compose logs -f celery_worker
docker compose logs --tail=100 quiz_backend

# Продакшн
docker compose -f docker-compose.local-prod.yml logs -f quiz_backend
docker compose -f docker-compose.local-prod.yml logs -f redis_cache_prod
docker compose -f docker-compose.local-prod.yml logs -f celery_worker_prod
docker compose -f docker-compose.local-prod.yml logs --tail=100 quiz_backend
```

### Зайти в контейнер
```bash
# Разработка
docker compose exec quiz_backend bash
docker compose exec redis sh
docker compose exec database bash

# Продакшн
docker compose -f docker-compose.local-prod.yml exec quiz_backend bash
docker compose -f docker-compose.local-prod.yml exec redis_cache_prod sh
docker compose -f docker-compose.local-prod.yml exec postgres_db bash
```

### Использование ресурсов
```bash
# Все контейнеры
docker stats

# Конкретный контейнер
docker stats quiz_backend

# Топ процессов внутри контейнера
docker compose exec quiz_backend top
```

---

## 🧹 Очистка

```bash
# Остановить и удалить контейнеры
docker compose down

# Также удалить volumes (ОСТОРОЖНО! Удалит БД!)
docker compose down -v

# Удалить неиспользуемые образы
docker image prune -f

# Удалить всё неиспользуемое
docker system prune -a

# Посмотреть занятое место
docker system df
```

---

## 🔄 Обновление после git pull

### Разработка
```bash
git pull origin main
docker compose down
docker compose build
docker compose up -d
docker compose run web python manage.py migrate
docker compose run web python manage.py collectstatic --noinput
```

### Продакшн
```bash
git pull origin main
./start-prod.sh
```

---

## 📊 Быстрая диагностика

```bash
# Всё ли работает?
docker compose ps  # или с -f docker-compose.local-prod.yml

# Redis живой?
docker compose exec redis redis-cli ping  # Ответ: PONG

# Celery работает?
docker compose exec celery_worker celery -A config inspect ping

# БД доступна?
docker compose exec database pg_isready -U postgres

# Сайт доступен?
curl -I http://localhost:8001  # или https://quiz-code.com

# Кэш работает?
docker compose run web python manage.py cache_monitor --test
```

---

## 🆘 Экстренное восстановление

```bash
# 1. Всё сломалось - полная перезагрузка
docker compose down
docker compose up -d --force-recreate

# 2. Redis глючит
docker compose restart redis

# 3. Celery не обрабатывает задачи
docker compose restart celery_worker celery_beat

# 4. Django не отвечает
docker compose restart quiz_backend

# 5. Статика не грузится
docker compose exec quiz_backend python manage.py collectstatic --noinput --clear
docker compose restart nginx

# 6. Кэш проблемы
docker compose run web python manage.py cache_monitor --clear
```

---

Сохраните эту шпаргалку - она сэкономит вам время! 🚀

