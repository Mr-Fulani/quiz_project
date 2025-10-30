# ⚡ Быстрый старт продакшена

## 🎯 Для нетерпеливых

```bash
# 1. Обновить код
git pull origin main

# 2. Запустить продакшн
./start-prod.sh

# 3. Проверить статус
docker compose -f docker-compose.local-prod.yml ps

# Готово! 🎉
```

---

## 📦 Что включено

После запуска будут работать:

- ✅ **PostgreSQL** - основная БД
- ✅ **Redis** (512MB) - кэш и очереди задач
- ✅ **Django** + Gunicorn (4 workers, 2 threads)
- ✅ **Celery Worker** (4 процесса) - фоновые задачи
- ✅ **Celery Beat** - планировщик задач
- ✅ **Mini App** - FastAPI приложение
- ✅ **Nginx** - веб-сервер с SSL
- ✅ **Telegram Bot** - бот для Telegram

---

## 🔍 Быстрая проверка

```bash
# Все ли контейнеры запущены?
docker compose -f docker-compose.local-prod.yml ps

# Redis работает?
docker compose -f docker-compose.local-prod.yml exec redis_cache_prod redis-cli ping
# Ответ: PONG

# Celery работает?
docker compose -f docker-compose.local-prod.yml exec celery_worker_prod celery -A config inspect ping
# Ответ: -> celery@hostname: OK

# Кэш работает?
docker compose -f docker-compose.local-prod.yml run quiz_backend python manage.py cache_monitor --test
# Ответ: ✅ Отличная производительность!

# Сайт доступен?
curl -I https://quiz-code.com
# Ответ: HTTP/2 200
```

---

## 🐛 Что-то пошло не так?

### Проблема: Redis не запускается
```bash
docker compose -f docker-compose.local-prod.yml restart redis_cache_prod
```

### Проблема: Celery не работает
```bash
docker compose -f docker-compose.local-prod.yml restart celery_worker_prod celery_beat_prod
```

### Проблема: Сайт медленный
```bash
# Проверить кэш
docker compose -f docker-compose.local-prod.yml run quiz_backend python manage.py cache_monitor --stats

# Очистить кэш и прогреть заново
docker compose -f docker-compose.local-prod.yml run quiz_backend python manage.py cache_monitor --clear
```

### Проблема: Статика не загружается
```bash
# Пересобрать статику
docker compose -f docker-compose.local-prod.yml exec quiz_backend python manage.py collectstatic --noinput --clear

# Перезапустить nginx
docker compose -f docker-compose.local-prod.yml restart nginx_local_prod
```

---

## 📊 Мониторинг

```bash
# Логи Django
docker compose -f docker-compose.local-prod.yml logs -f quiz_backend

# Логи Celery
docker compose -f docker-compose.local-prod.yml logs -f celery_worker_prod

# Все логи
docker compose -f docker-compose.local-prod.yml logs -f

# Использование ресурсов
docker stats
```

---

## 📚 Дополнительная документация

- `PRODUCTION_SETUP.md` - полная инструкция
- `PRODUCTION_DEPLOYMENT_CHECKLIST.md` - чеклист деплоя
- `DJANGO_CELERY_README.md` - работа с Celery
- `PRODUCTION_IMPROVEMENTS_SUMMARY.md` - что изменено

---

## 💡 Полезные команды

```bash
# Перезапустить все
docker compose -f docker-compose.local-prod.yml restart

# Остановить все
docker compose -f docker-compose.local-prod.yml down

# Посмотреть логи за последние 50 строк
docker compose -f docker-compose.local-prod.yml logs --tail=50

# Зайти в контейнер Django
docker compose -f docker-compose.local-prod.yml exec quiz_backend bash

# Выполнить Django команду
docker compose -f docker-compose.local-prod.yml exec quiz_backend python manage.py <command>
```

---

**Готово! Ваш продакшн запущен и оптимизирован 🚀**

