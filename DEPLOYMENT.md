# 🚀 Инструкции по развертыванию

## 📋 Обзор

Проект настроен для работы в двух режимах:
- **Локальная разработка** - без SSL сертификатов
- **Продакшен** - с SSL сертификатами Let's Encrypt

## 🔧 Локальная разработка

### Запуск
```bash
./start-local.sh
```

### Что происходит:
- Запускаются все сервисы с локальной конфигурацией
- SSL сертификаты НЕ используются
- Доступ по HTTP на локальных портах

### Доступные сервисы:
- Backend: http://localhost:8001
- Mini App: http://localhost:8080
- Telegram Bot: http://localhost:8002
- Database: localhost:5433

### Остановка
```bash
docker compose down
```

## 🌐 Продакшен развертывание

### Первый запуск (получение SSL сертификатов)
```bash
./start-prod.sh
```

### Что происходит:
1. Проверяется наличие SSL сертификатов
2. Если сертификатов нет - они получаются через Let's Encrypt
3. Если сертификаты есть - они используются
4. Запускаются все сервисы с SSL

### Повторные запуски
```bash
./start-prod.sh
```

**Важно:** Сертификаты сохраняются и НЕ пересоздаются при каждом запуске!

### Переменные окружения безопасности (`.env`)

| Переменная | Обязательна | Назначение |
|---|---|---|
| `REDIS_PASSWORD` | **да** — без неё `docker-compose.local-prod.yml` не стартует | пароль Redis (`requirepass`); подставляется в `REDIS_URL`/`CELERY_*`. Используйте символы, безопасные для URL (без `@ : / ?`) |
| `WALLET_PAY_API_KEY` | да, если включён Wallet Pay | при пустом значении webhook Wallet Pay отклоняется |
| `COINGATE_API_TOKEN` | да, если включён CoinGate | callback CoinGate проверяется запросом статуса заказа к API |
| `SOCIAL_MEDIA_CALLBACK_SECRET` | нет | если задан — Make.com должен присылать его в заголовке `X-Callback-Secret` |
| `TELEGRAM_INIT_DATA_MAX_AGE` | нет (86400) | срок действия initData Mini App, секунды |
| `BOT_DEFAULT_TENANT_SLUG` | нет | какой тенант обслуживает глобальный `TELEGRAM_BOT_TOKEN`, если он не указан ни у одного тенанта (иначе — единственный тенант без своего токена) |
| `CORS_ALLOWED_ORIGINS` (mini_app) | нет | дополнительные CORS-источники для FastAPI через запятую; по умолчанию чужим сайтам доступ закрыт |

Также у каждого тенанта в админке должен быть заполнен `bot_token` — им проверяется подпись Mini App,
бот тенанта запускается в общем процессе бота и выполняет Telegram-действия сайта
(при пустом поле используется глобальный `TELEGRAM_BOT_TOKEN`). После изменения `bot_token`
перезапустите контейнер бота.

### Порты
В `docker-compose.local-prod.yml` порты Postgres (5433), backend (8001), mini_app (8080) и бота (8002)
слушают только `127.0.0.1`: снаружи всё идёт через nginx (80/443). Redis наружу не публикуется.
С самого сервера доступ сохраняется: `curl http://localhost:8001/health/`.

## 🔐 SSL Сертификаты

### Автоматическое управление
- Сертификаты автоматически получаются при первом запуске
- Сертификаты сохраняются в `./certbot/conf/`
- Сертификаты НЕ удаляются при перезапуске
- Сертификаты НЕ коммитятся в git

### Ручное обновление сертификатов
```bash
# Использовать скрипт для обновления (рекомендуется)
./renew-ssl.sh

# Или вручную через docker compose
docker compose -f docker-compose.local-prod.yml run --rm --entrypoint "" certbot sh -c "/usr/local/bin/certbot renew"
docker compose -f docker-compose.local-prod.yml exec nginx nginx -s reload
```

### Автоматическое обновление сертификатов

Let's Encrypt сертификаты действительны 90 дней. Рекомендуется настроить автоматическое обновление.

#### Настройка автоматического обновления через cron

```bash
# Запустите скрипт настройки (один раз)
./setup-ssl-auto-renewal.sh
```

Этот скрипт:
- Создаст cron задачу для ежедневной проверки и обновления сертификатов (в 03:00)
- Настроит логирование в `/var/log/ssl-renewal.log`
- Автоматически перезагрузит nginx после обновления

#### Проверка статуса автоматического обновления

```bash
# Просмотр cron задач
crontab -l | grep renew-ssl

# Просмотр логов
tail -f /var/log/ssl-renewal.log

# Ручной запуск автоматического скрипта
./renew-ssl-auto.sh
```

#### Удаление автоматического обновления

```bash
# Удалить cron задачу
crontab -l | grep -v "renew-ssl-auto.sh" | crontab -
```

### Сброс сертификатов (полное удаление)
```bash
# ОСТОРОЖНО! Это удалит все сертификаты
sudo rm -rf ./certbot/conf/
./start-prod.sh
```

## 📁 Структура файлов

### Конфигурации Nginx
- `nginx/nginx-local.conf` - для локальной разработки
- `nginx/nginx-prod.conf` - для продакшена (с SSL)
- `nginx/nginx-temp.conf` - временная (только для получения сертификатов)

### Docker Compose
- `docker-compose.yml` - локальная разработка (`start-local.sh`)
- `docker-compose.local-prod.yml` - продакшен (используется `start-prod.sh`)

### Тесты backend без Docker
Миграции содержат Postgres-специфичный SQL, поэтому для прогона на SQLite есть
`config/test_settings_sqlite.py` (SQLite в памяти, таблицы из моделей):
```bash
cd quiz_backend && DEBUG=True SECRET_KEY=test TELEGRAM_BOT_TOKEN=000:test pytest --ds=config.test_settings_sqlite tenants accounts/tests blog/tests donation/tests.py social_auth/tests.py webhooks/tests.py
```
Внутри Docker (Postgres) — обычный `pytest`.

### Скрипты
- `start-local.sh` - запуск локальной разработки
- `start-prod.sh` - запуск продакшена
- `renew-ssl.sh` - ручное обновление SSL сертификатов (с dry-run)
- `renew-ssl-auto.sh` - автоматическое обновление SSL сертификатов (для cron)
- `setup-ssl-auto-renewal.sh` - настройка автоматического обновления через cron

## ⚠️ Важные замечания

### Git и сертификаты
- Сертификаты добавлены в `.gitignore`
- Сертификаты НЕ должны коммититься в git
- При `git pull` сертификаты НЕ затрагиваются

### Перезапуск сервера
- При перезапуске сервера сертификаты сохраняются
- Используйте `./start-prod.sh` для запуска после перезагрузки

### Домены
- Текущие домены: `quiz-code.com`, `www.quiz-code.com`, `mini.quiz-code.com`
- Для добавления новых доменов измените `DOMAINS` в `start-prod.sh`

## 🛠️ Устранение неполадок

### Проблемы с SSL
1. Проверьте DNS настройки доменов
2. Убедитесь, что домены указывают на ваш сервер
3. Проверьте логи: `docker compose logs nginx`

### Проблемы с сертификатами
1. Проверьте наличие сертификатов: `ls -la ./certbot/conf/live/`
2. Проверьте логи Certbot: `cat certbot_debug.log`

### Сброс сертификатов
```bash
# ОСТОРОЖНО! Это удалит все сертификаты
sudo rm -rf ./certbot/conf/
./start-prod.sh
```

## 🛡️ Безопасность и защита от ботов

Для защиты от DDoS и сканеров ботов на сервере внедрено несколько уровней защиты:

1. **Hetzner Firewall**: На внешнем уровне разрешены подключения к портам 80/443 только от IP-адресов Cloudflare.
2. **Fail2ban**: Автоматическая блокировка IP при обнаружении попыток сканирования.
3. **Nginx Hardening**: Ограничения соединений, запросов и SSL handshake.

Подробные инструкции по настройке и управлению защитой смотрите в [INFRASTRUCTURE_HARDENING.md](INFRASTRUCTURE_HARDENING.md).

### Быстрая настройка Fail2ban на сервере:
```bash
chmod +x scripts/setup-fail2ban.sh
./scripts/setup-fail2ban.sh
```

## 📞 Поддержка

При возникновении проблем:
1. Проверьте логи сервисов
2. Убедитесь в правильности DNS настроек
3. Проверьте доступность портов 80 и 443
