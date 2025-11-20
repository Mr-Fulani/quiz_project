# ⚠️ СРОЧНО: Запустите это сейчас

После того как вы обновили код и пересобрали контейнер, но все еще видите ошибку 500:

## 1. Запустите скрипт проверки логов Gunicorn

```bash
./CHECK_GUNICORN_LOGS.sh
```

Этот скрипт проверит:
- Есть ли `print()` в коде контейнера
- Логи Gunicorn из файлов (не из stdout)
- Поиск ошибок и traceback

## 2. Если скрипт не работает, выполните вручную:

```bash
# Проверить что print() есть в коде
docker compose -f docker-compose.local-prod.yml exec quiz_backend grep -c "print(" /app/social_auth/views.py

# Посмотреть error.log Gunicorn
docker compose -f docker-compose.local-prod.yml exec quiz_backend tail -200 /app/logs/gunicorn-error.log

# Поиск TELEGRAM в error.log
docker compose -f docker-compose.local-prod.yml exec quiz_backend grep -A 50 "TELEGRAM AUTH POST\|POST Request\|ERROR\|Traceback" /app/logs/gunicorn-error.log | tail -150
```

## 3. Попробуйте авторизоваться снова

После запуска скрипта:
1. Откройте сайт в браузере
2. Сделайте жесткую перезагрузку: `Ctrl + Shift + R`
3. Попробуйте авторизоваться через Telegram
4. Сразу после попытки запустите `./CHECK_GUNICORN_LOGS.sh` снова

## 4. Пришлите полный вывод

Пришлите полный вывод команды:
```bash
./CHECK_GUNICORN_LOGS.sh
```

Особенно важны:
- Количество `print()` в коде (должно быть > 0)
- Содержимое `gunicorn-error.log`
- Любые строки с "TELEGRAM", "ERROR", "Traceback"

## Если логи все еще пустые

Возможно проблема в том что:
1. Контейнер не пересобрался - проверьте: `docker compose -f docker-compose.local-prod.yml images quiz_backend`
2. Нужно пересобрать без кэша: `docker compose -f docker-compose.local-prod.yml build --no-cache quiz_backend && docker compose -f docker-compose.local-prod.yml up -d quiz_backend`
3. Запрос не доходит до Django - проверьте nginx логи: `docker compose -f docker-compose.local-prod.yml logs nginx --tail=50`

