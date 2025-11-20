# Инструкции для проверки на сервере

## Проблема
Из логов nginx видно что запрос идет на `/api/social-auth/telegram/auth` но возвращается ошибка "Нет данных от Telegram виджета". Это означает что Telegram не передает данные в query параметрах.

## Шаги для проверки на сервере

### 1. Обновить код и пересобрать контейнер

```bash
cd /opt/quiz_project/quiz_project
git fetch origin
git checkout fix/telegram-auth-issue
git pull origin fix/telegram-auth-issue

# Пересобрать только quiz_backend контейнер
docker compose -f docker-compose.local-prod.yml up -d --build quiz_backend
```

### 2. Проверить что исправления применились

```bash
# Запустить скрипт проверки
./CHECK_TELEGRAM_LOGS.sh

# Или вручную проверить:
docker compose -f docker-compose.local-prod.yml exec quiz_backend grep -c "Raw data (обработанные)" /app/social_auth/views.py
# Должно вернуть: 1 (если исправления применены)
```

### 3. Проверить логи Django при попытке авторизации

```bash
# В одном терминале запустить мониторинг логов
docker compose -f docker-compose.local-prod.yml logs -f quiz_backend | grep -i "telegram"

# В другом терминале или в браузере попробовать авторизоваться через Telegram
# Затем посмотреть что появилось в логах
```

### 4. Проверить детальные логи последнего запроса

```bash
# Посмотреть последние логи с детальной информацией
docker compose -f docker-compose.local-prod.yml logs quiz_backend --tail=500 | grep -A 30 "TELEGRAM AUTH GET REQUEST" | tail -80
```

### 5. Основная проблема - домен не настроен в BotFather

Из логов nginx видно что Telegram делает redirect но **не передает данные**. Это происходит когда:

1. **Домен не настроен в BotFather** - это самая частая причина
2. Telegram не передает данные в query параметрах если домен не добавлен

**Решение:**
1. Откройте @BotFather в Telegram
2. Выполните команду `/setdomain`
3. Выберите вашего бота (mr_proger_bot)
4. Укажите домен: `quiz-code.com` (без https:// и без /)
5. Подтвердите

После настройки домена Telegram начнет передавать данные в query параметрах при redirect.

### 6. Проверить настройки бота в контейнере

```bash
# Проверить что TELEGRAM_BOT_TOKEN и TELEGRAM_BOT_USERNAME установлены
docker compose -f docker-compose.local-prod.yml exec quiz_backend env | grep TELEGRAM
```

### 7. Что должно быть в логах после исправлений

После применения исправлений в логах должно появиться:

```
=== TELEGRAM AUTH GET REQUEST ===
Request method: GET
Request GET params: {...}
Raw data (обработанные): {...}
Request query string: id=...&hash=...
```

Если видите "НЕТ ДАННЫХ ОТ TELEGRAM ВИДЖЕТА!" - значит данные не приходят от Telegram, нужно настроить домен в BotFather.

### 8. Проверить что контейнер пересобрался

```bash
# Проверить время последней пересборки
docker compose -f docker-compose.local-prod.yml images quiz_backend

# Пересобрать принудительно без кэша
docker compose -f docker-compose.local-prod.yml build --no-cache quiz_backend
docker compose -f docker-compose.local-prod.yml up -d quiz_backend
```

## Важно

Логи Django **НЕ** выводятся в консоль браузера. Они только в логах Docker контейнера. Чтобы увидеть логи нужно использовать команды выше.

## Если данные все еще не приходят

1. Убедитесь что домен настроен в BotFather: `/setdomain` → выберите бота → `quiz-code.com`
2. Проверьте что используется правильный bot_id в URL OAuth
3. Попробуйте очистить кэш браузера и попробовать снова
4. Проверьте что в BotFather указан именно домен `quiz-code.com` без протокола и слешей

