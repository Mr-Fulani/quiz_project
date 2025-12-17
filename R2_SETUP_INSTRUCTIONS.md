# Инструкция по настройке Cloudflare R2

## Текущая структура бакета

Бакет: `quiz-hub-prod`

Структура директорий:
```
quiz-hub-prod/
 ├── prod/
 │    ├── images/
 │    ├── videos/
 │    └── tmp/
 └── dev/
      ├── images/
      ├── videos/
      └── tmp/
```

## Настройка переменных окружения

Добавьте следующие переменные в ваш `.env` файл:

```bash
# Включение R2 хранилища
USE_R2_STORAGE=True

# Cloudflare R2 учетные данные
R2_ACCOUNT_ID=your_account_id_here
R2_ACCESS_KEY_ID=your_access_key_id_here
R2_SECRET_ACCESS_KEY=your_secret_access_key_here

# Имя бакета (уже настроено по умолчанию)
R2_BUCKET_NAME=quiz-hub-prod

# Публичный домен (опционально, если настроен кастомный домен)
# R2_PUBLIC_DOMAIN=your-custom-domain.com

# Для бота: окружение (dev или prod, по умолчанию dev)
# BOT_ENV=dev  # или prod для продакшена
```

## Автоматическое определение окружения

Система автоматически определяет окружение:

- **Django backend**: 
  - `prod/` если `DEBUG=False`
  - `dev/` если `DEBUG=True`

- **Telegram bot**:
  - По умолчанию использует `dev/`
  - Можно переопределить через переменную `BOT_ENV=prod`

## Структура хранения файлов

При загрузке файлов они автоматически сохраняются в правильную директорию:

- **Изображения**: `{env}/images/{filename}`
  - Пример: `prod/images/python_basics_en_123.png`
  - Пример: `dev/images/python_basics_en_123.png`

- **Видео**: `{env}/videos/{filename}`
  - Пример: `prod/videos/python_basics_en_123.mp4`
  - Пример: `dev/videos/python_basics_en_123.mp4`

## Проверка настройки

После добавления переменных окружения:

1. Перезапустите контейнеры:
```bash
docker compose restart quiz_backend telegram_bot
```

2. Проверьте логи на наличие сообщения:
```
R2 хранилище настроено: бакет=quiz-hub-prod, окружение=prod
```
или
```
R2 хранилище настроено: бакет=quiz-hub-prod, окружение=dev
```

3. Попробуйте загрузить тестовое изображение через админку Django

## Миграция данных из S3

Если у вас есть данные в S3, которые нужно мигрировать:

```bash
# 1. Миграция файлов (с указанием целевого окружения)
docker compose run --rm quiz_backend python manage.py migrate_s3_to_r2 --target-env prod

# 2. Обновление URL в базе данных
docker compose run --rm quiz_backend python manage.py migrate_s3_to_r2_urls

# 3. Регенерация нерабочих изображений (если нужно)
docker compose run --rm quiz_backend python manage.py regenerate_broken_images
```

## Важные замечания

1. **Окружения разделены**: Файлы из `dev/` не будут видны в `prod/` и наоборот
2. **Безопасность**: Убедитесь, что `.env` файл не попадает в git (должен быть в `.gitignore`)
3. **Публичный доступ**: Если используете кастомный домен, настройте его в Cloudflare R2
4. **Бэкапы**: Рекомендуется делать регулярные бэкапы важных данных

## Получение учетных данных R2

1. Войдите в Cloudflare Dashboard
2. Перейдите в R2 Object Storage
3. Выберите ваш бакет `quiz-hub-prod`
4. Перейдите в "Manage R2 API Tokens"
5. Создайте новый токен с правами:
   - Object Read & Write
   - Object List
6. Скопируйте:
   - **Account ID** (находится в URL или в настройках аккаунта)
   - **Access Key ID**
   - **Secret Access Key**

## Troubleshooting

### Ошибка: "R2_ACCOUNT_ID не установлен"
- Проверьте, что переменная `R2_ACCOUNT_ID` добавлена в `.env`
- Перезапустите контейнеры

### Ошибка: "R2 настройки не сконфигурированы"
- Убедитесь, что все три переменные установлены: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`
- Проверьте правильность значений (без пробелов, кавычек)

### Файлы загружаются не в ту директорию
- Проверьте значение `DEBUG` в Django (для backend)
- Проверьте значение `BOT_ENV` для бота
- Убедитесь, что `USE_R2_STORAGE=True`

