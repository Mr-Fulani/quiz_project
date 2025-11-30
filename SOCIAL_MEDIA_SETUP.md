# Быстрая настройка интеграции с соцсетями

## Шаг 1: Применить миграции

```bash
# Остановите контейнеры на порту 5433 если они мешают
docker ps | grep 5433

# Или измените порт в docker-compose.yml и запустите:
docker compose up -d database redis

# Примените миграции
docker compose exec quiz_backend python manage.py migrate tasks
docker compose exec quiz_backend python manage.py migrate webhooks

# Или если контейнер не запущен:
docker compose run --rm quiz_backend python manage.py migrate tasks
docker compose run --rm quiz_backend python manage.py migrate webhooks
```

---

## Шаг 2: Перезапустите сервисы

```bash
docker compose restart quiz_backend
docker compose restart celery_worker
```

---

## Шаг 3: Настройте credentials (для API платформ)

### Pinterest
1. Откройте Django админку → **Webhooks** → **Social Media Credentials**
2. Нажмите **Добавить Social Media Credentials**
3. Заполните:
   - **Platform:** Pinterest
   - **Access Token:** ваш токен из https://developers.pinterest.com/
   - **Extra Data:** `{"board_id": "your-board-id"}`
   - **Is Active:** ✅
4. Сохраните

### Яндекс Дзен
- **Platform:** Яндекс Дзен  
- **Access Token:** OAuth токен
- **Extra Data:** `{"channel_id": "your-channel-id"}`

### Facebook
- **Platform:** Facebook
- **Access Token:** Page Access Token
- **Extra Data:** `{"page_id": "your-page-id"}`

---

## Шаг 4: Настройте webhook (для Instagram/TikTok/YouTube)

1. Создайте сценарий в Make.com с Webhook триггером
2. В Django админке → **Webhooks** → **Webhooks** → Добавить:
   - **Service Name:** "Make.com Social"
   - **URL:** ваш Make.com webhook URL
   - **Webhook Type:** "Социальные сети"
   - **Target Platforms:** `["instagram", "tiktok", "youtube_shorts"]`
   - **Is Active:** ✅

---

## Шаг 5: Тест

1. Создайте задачу через админку или бота
2. Установите `published=True`
3. Проверьте логи:
   ```bash
   docker compose exec quiz_backend tail -f /app/quiz_backend_logs/debug.log
   ```
4. В логах должно появиться: "🌐 Автопубликация задачи X в соцсети"
5. Проверьте **Tasks → Social Media Posts** - должны появиться записи

---

## Альтернативный метод: Ручная публикация

1. Откройте админку → **Tasks → Tasks**
2. Выберите задачи
3. Actions → **📱 Опубликовать в соцсети**
4. Go

---

## Что реализовано

✅ Модели для отслеживания публикаций  
✅ API интеграции: Pinterest, Яндекс Дзен, Facebook  
✅ Webhook интеграция для Instagram, TikTok, YouTube  
✅ Автоматическая публикация через Django сигналы  
✅ Админка для управления credentials и webhook  
✅ Inline просмотр публикаций в задаче  
✅ Action для ручной публикации  
✅ Callback endpoint для статусов от Make.com  
✅ Retry logic и обработка ошибок  

---

## Дополнительная информация

Подробная документация: [`SOCIAL_MEDIA_INTEGRATION.md`](SOCIAL_MEDIA_INTEGRATION.md)

