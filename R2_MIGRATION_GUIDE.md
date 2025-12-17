# Руководство по миграции с AWS S3 на Cloudflare R2

## Обзор

Проект поддерживает хранение изображений и видео в двух хранилищах:
- **AWS S3** (старое хранилище)
- **Cloudflare R2** (новое хранилище, рекомендуется)

R2 совместим с S3 API, что упрощает миграцию. Основные преимущества R2:
- **Нет платы за трафик** (egress) - плата только за хранение
- **Бесплатный CDN** через Cloudflare
- **Совместимость с S3 API** - минимальные изменения в коде

## Настройка Cloudflare R2

### 1. Создание бакета в R2

1. Войдите в панель Cloudflare
2. Перейдите в раздел R2 Object Storage
3. Создайте новый бакет
4. Запишите имя бакета

### 2. Получение учетных данных

1. В разделе R2 найдите "Manage R2 API Tokens"
2. Создайте новый API токен с правами на чтение/запись
3. Запишите:
   - **Account ID** (находится в URL или в настройках аккаунта)
   - **Access Key ID**
   - **Secret Access Key**

### 3. Настройка публичного домена (опционально)

Для использования кастомного домена:
1. Настройте Custom Domain в R2 или используйте Cloudflare Workers
2. Запишите публичный домен

## Переменные окружения

Добавьте следующие переменные в `.env` файл:

```bash
# Переключение на R2 (True для R2, False для S3)
USE_R2_STORAGE=True

# Cloudflare R2 настройки
R2_ACCOUNT_ID=your_account_id
R2_ACCESS_KEY_ID=your_access_key_id
R2_SECRET_ACCESS_KEY=your_secret_access_key
R2_BUCKET_NAME=your_bucket_name
R2_PUBLIC_DOMAIN=your-public-domain.com  # Опционально, если используется кастомный домен

# Старые S3 настройки (оставьте для обратной совместимости или миграции)
AWS_ACCESS_KEY_ID=your_aws_key  # Используется только если USE_R2_STORAGE=False
AWS_SECRET_ACCESS_KEY=your_aws_secret
S3_BUCKET_NAME=your_s3_bucket
S3_REGION=us-east-1
```

## Миграция данных

### Шаг 1: Миграция файлов из S3 в R2

Используйте команду для копирования всех файлов:

```bash
# Проверка без реальной миграции
docker compose run --rm quiz_backend python manage.py migrate_s3_to_r2 --dry-run

# Миграция всех файлов
docker compose run --rm quiz_backend python manage.py migrate_s3_to_r2

# Миграция только изображений
docker compose run --rm quiz_backend python manage.py migrate_s3_to_r2 --prefix images/

# Ограничение количества файлов (для тестирования)
docker compose run --rm quiz_backend python manage.py migrate_s3_to_r2 --limit 100
```

### Шаг 2: Обновление URL в базе данных

После миграции файлов обновите URL в базе данных:

```bash
# Проверка без изменений
docker compose run --rm quiz_backend python manage.py migrate_s3_to_r2_urls --dry-run

# Обновление URL
docker compose run --rm quiz_backend python manage.py migrate_s3_to_r2_urls

# С указанием старого и нового домена
docker compose run --rm quiz_backend python manage.py migrate_s3_to_r2_urls \
  --old-domain bucket.s3.region.amazonaws.com \
  --new-domain your-r2-domain.com
```

### Шаг 3: Восстановление нерабочих ссылок

Для задач с нерабочими ссылками на изображения:

```bash
# Проверка без регенерации
docker compose run --rm quiz_backend python manage.py regenerate_broken_images --dry-run

# Регенерация всех нерабочих изображений
docker compose run --rm quiz_backend python manage.py regenerate_broken_images

# Регенерация только задач с определенным S3 доменом
docker compose run --rm quiz_backend python manage.py regenerate_broken_images \
  --check-s3-domain bucket.s3.region.amazonaws.com

# Регенерация конкретных задач
docker compose run --rm quiz_backend python manage.py regenerate_broken_images \
  --task-ids 1,2,3,4,5

# Ограничение количества (для тестирования)
docker compose run --rm quiz_backend python manage.py regenerate_broken_images --limit 100
```

## Структура хранения в R2

Файлы хранятся в следующей структуре:

```
r2-bucket/
  ├── images/
  │   └── {topic}_{subtopic}_{language}_{task_id}.png
  └── videos/
      └── {topic}_{subtopic}_{language}_{task_id}.mp4
```

## Особенности R2

### Оптимизация под R2

Поскольку в R2 нет платы за трафик, но есть плата за хранение:

1. **Оптимизация размера файлов:**
   - Изображения автоматически оптимизируются при загрузке (PNG optimize)
   - Для будущих видео используйте эффективные кодеки (H.264, VP9)

2. **Использование преимуществ:**
   - Можно использовать прямые ссылки без ограничений по трафику
   - Не нужно экономить на количестве запросов
   - CDN Cloudflare ускоряет доступ (бесплатно)

### Кэширование

URL изображений кэшируются в Redis для производительности (не для экономии трафика):
- Ключ кэша: `task_image_url:{task_id}`
- TTL: 24 часа
- Автоматическая инвалидация при обновлении задачи

## Подготовка к генерации видео

Проект подготовлен к будущей генерации видео:

1. **Модель Task** содержит поле `video_url`
2. **Сервисы** поддерживают загрузку видео через `upload_video_to_r2()`
3. **Структура хранения** включает директорию `videos/`

После внедрения генерации видео:
- Используйте `upload_video_to_r2()` для загрузки видео
- Команда `regenerate_broken_images` будет поддерживать опцию `--include-videos`

## Откат на S3

Если нужно вернуться на S3:

1. Установите `USE_R2_STORAGE=False` в `.env`
2. Убедитесь, что старые S3 настройки присутствуют
3. Перезапустите сервисы

## Проверка работы

После миграции проверьте:

1. Загрузка новых изображений работает через R2
2. Старые URL обновлены в базе данных
3. Изображения доступны по новым URL
4. Нет ошибок в логах

## Поддержка

При возникновении проблем:

1. Проверьте логи: `docker compose logs quiz_backend`
2. Убедитесь, что все переменные окружения установлены
3. Проверьте доступность R2 бакета
4. Используйте `--dry-run` для безопасной проверки команд

