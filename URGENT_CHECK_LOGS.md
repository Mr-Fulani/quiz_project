# СРОЧНО: Проверка логов после обновления

## Проблема
После возврата из Telegram появляется ошибка 500, но логи Django не видны в `docker compose logs`.

## Решение
Добавлен `print()` с `flush=True` для гарантированного вывода логов даже если `logger` не работает.

## Команды для применения на сервере

### 1. Обновить код
```bash
cd /opt/quiz_project/quiz_project
git pull origin fix/telegram-auth-issue
```

### 2. Пересобрать quiz_backend
```bash
docker compose -f docker-compose.local-prod.yml up -d --build quiz_backend
```

### 3. Проверить что новый код в контейнере
```bash
# Проверить что print() добавлен
docker compose -f docker-compose.local-prod.yml exec quiz_backend grep -c "print(" /app/social_auth/views.py

# Должно показать число больше 0
```

### 4. После попытки авторизации - проверить логи

#### Вариант 1: Скрипт для проверки логов Gunicorn
```bash
./CHECK_GUNICORN_LOGS.sh
```

#### Вариант 2: Вручную проверить логи Gunicorn
```bash
# Проверить error.log Gunicorn
docker compose -f docker-compose.local-prod.yml exec quiz_backend tail -200 /app/logs/gunicorn-error.log

# Проверить stdout/stderr контейнера
docker compose -f docker-compose.local-prod.yml logs quiz_backend --tail=300 | grep -A 10 "TELEGRAM AUTH POST\|POST Request\|ERROR\|Traceback"
```

#### Вариант 3: Смотреть логи в реальном времени
```bash
# В одном терминале запустить
docker compose -f docker-compose.local-prod.yml logs -f quiz_backend

# В другом терминале попробовать авторизоваться через Telegram
# Должны появиться строки с "=== TELEGRAM AUTH POST REQUEST ==="
```

## Что должно появиться в логах

После попытки авторизации должны появиться строки:
```
================================================================================
=== TELEGRAM AUTH POST REQUEST ===
================================================================================
POST Request: POST /api/social-auth/telegram/auth/
Request body (raw): {...}
Данные получены из request.body (JSON): {...}
Обработанные данные авторизации: {...}
Данные прошли валидацию: {...}
Вызываем TelegramAuthService.process_telegram_auth...
Пользователь получен: ..., id=..., is_active=True
Вызываем login() для пользователя ...
Сессия сохранена: ...
Начинаем сериализацию данных для ответа...
Пользователь сериализован: ...
Ответ подготовлен: success=True, user_id=..., username=...
Создаем Response с данными: {...}
Response создан успешно
```

Если появляется ошибка, должны быть строки:
```
ERROR: ...
Traceback: ...
КРИТИЧЕСКАЯ ОШИБКА В POST TelegramAuthView
```

## Если логи все еще не видны

1. Проверить что контейнер пересобрался:
```bash
docker compose -f docker-compose.local-prod.yml ps quiz_backend
docker compose -f docker-compose.local-prod.yml images quiz_backend
```

2. Пересобрать без кэша:
```bash
docker compose -f docker-compose.local-prod.yml build --no-cache quiz_backend
docker compose -f docker-compose.local-prod.yml up -d quiz_backend
```

3. Проверить что print() работает:
```bash
docker compose -f docker-compose.local-prod.yml exec quiz_backend python -c "print('TEST', flush=True)"
```

4. Прислать полный вывод `./CHECK_GUNICORN_LOGS.sh`

