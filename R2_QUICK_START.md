# Быстрый старт с Cloudflare R2

## Шаг 1: Добавьте переменные в .env

```bash
# Включение R2
USE_R2_STORAGE=True

# Ваши учетные данные R2
R2_ACCOUNT_ID=ваш_account_id
R2_ACCESS_KEY_ID=ваш_access_key_id
R2_SECRET_ACCESS_KEY=ваш_secret_access_key

# Бакет (уже настроен по умолчанию)
R2_BUCKET_NAME=quiz-hub-prod
```

## Шаг 2: Перезапустите контейнеры

```bash
docker compose restart quiz_backend telegram_bot
```

## Шаг 3: Проверьте работу

Проверьте логи:
```bash
docker compose logs quiz_backend | grep "R2 хранилище"
```

Должно быть сообщение:
```
R2 хранилище настроено: бакет=quiz-hub-prod, окружение=prod
```

## Готово! 

Теперь все новые изображения будут загружаться в R2:
- **Продакшен** (DEBUG=False): `prod/images/` и `prod/videos/`
- **Разработка** (DEBUG=True): `dev/images/` и `dev/videos/`

## Для бота

По умолчанию бот использует `dev/`. Чтобы использовать `prod/`, добавьте:
```bash
BOT_ENV=prod
```

## Миграция существующих данных

Если нужно мигрировать данные из S3:
```bash
# Миграция файлов
docker compose run --rm quiz_backend python manage.py migrate_s3_to_r2 --target-env prod

# Обновление URL в БД
docker compose run --rm quiz_backend python manage.py migrate_s3_to_r2_urls
```

