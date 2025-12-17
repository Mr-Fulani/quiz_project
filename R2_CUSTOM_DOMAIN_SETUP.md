# Настройка Custom Domain для Cloudflare R2

## Проблема

R2 endpoint URL (`https://account-id.r2.cloudflarestorage.com`) **не поддерживает публичный HTTPS доступ** через браузер. Он предназначен только для S3 API операций (загрузка, удаление через boto3).

## Почему Custom Domain обязателен?

В проекте медиафайлы используются **тремя компонентами**, и всем нужен публичный HTTPS URL:

1. **Telegram Bot** - отправляет изображения через `bot.send_photo(photo=image_url)`
   - Telegram Bot API требует публичный HTTPS URL для загрузки изображений
   
2. **Telegram Mini App** - отображает изображения через HTML `<img src="{{ image_url }}">`
   - Браузер в Telegram требует публичный HTTPS URL для отображения медиа
   
3. **Django Backend** - возвращает `image_url` в API ответах
   - Веб-интерфейс и внешние вебхуки используют эти URL

**Без Custom Domain ни один из компонентов не сможет получить доступ к медиафайлам!**

Для публичного доступа к файлам через браузер, Telegram Bot API и мини-апп **обязательно нужен Custom Domain**.

## Решение: Настройка Custom Domain

### Вариант 1: Custom Domain через Cloudflare Dashboard (Рекомендуется)

1. **В Cloudflare Dashboard:**
   - Перейдите в **R2** → выберите ваш бакет `quiz-hub-prod`
   - Перейдите в раздел **Settings** → **Public Access**
   - Нажмите **Connect Domain** или **Add Custom Domain**

2. **Настройка домена:**
   - Выберите домен из вашего Cloudflare аккаунта (например, `quiz-code.com`)
   - Создайте поддомен для R2, например: `cdn.quiz-code.com` или `media.quiz-code.com`
   - Cloudflare автоматически настроит DNS записи

3. **Добавьте в .env:**
   ```bash
   R2_PUBLIC_DOMAIN=cdn.quiz-code.com
   ```
   (или ваш выбранный поддомен)

### Вариант 2: Cloudflare Workers (Альтернатива)

Если не хотите использовать поддомен, можно создать Cloudflare Worker для проксирования:

1. Создайте Worker в Cloudflare Dashboard
2. Используйте код для проксирования запросов к R2
3. Настройте маршрут на ваш домен (например, `/media/*`)

**Пример Worker кода:**
```javascript
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const key = url.pathname.slice(1); // Убираем ведущий /
    
    const object = await env.R2_BUCKET.get(key);
    if (object === null) {
      return new Response('Object Not Found', { status: 404 });
    }
    
    const headers = new Headers();
    object.writeHttpMetadata(headers);
    headers.set('etag', object.httpEtag);
    
    return new Response(object.body, {
      headers,
    });
  },
};
```

### Вариант 3: Временное решение (только для разработки)

Для локальной разработки можно временно использовать ваш основной домен с проксированием через Nginx:

1. Настройте Nginx для проксирования запросов к R2 через Cloudflare API
2. Используйте путь типа `/r2-media/` на вашем основном домене

**⚠️ Не рекомендуется для продакшена** - лучше использовать Custom Domain.

## После настройки Custom Domain

1. **Добавьте в .env на сервере:**
   ```bash
   R2_PUBLIC_DOMAIN=cdn.quiz-code.com
   ```

2. **Перезапустите контейнеры:**
   ```bash
   docker compose restart quiz_backend telegram_bot
   ```

3. **Проверьте логи:**
   ```bash
   docker compose logs quiz_backend | grep "R2 публичный домен"
   ```

   Должно быть:
   ```
   R2 публичный домен настроен: cdn.quiz-code.com
   ```

4. **Проверьте доступность:**
   - Загрузите тестовое изображение через админку
   - Проверьте, что URL работает в браузере

## Важные замечания

- **Custom Domain обязателен** для всех компонентов:
  - ✅ Telegram Bot (отправка фото через Bot API)
  - ✅ Telegram Mini App (отображение изображений в браузере)
  - ✅ Django Backend (API ответы с URL медиа)
  - ✅ Внешние вебхуки (используют URL из API)
  
- Endpoint URL (`*.r2.cloudflarestorage.com`) работает **только для API операций** (загрузка/удаление через boto3/aioboto3)
- Без Custom Domain:
  - ❌ Файлы загружаются в R2, но публичные URL недоступны
  - ❌ Telegram Bot не сможет отправить фото
  - ❌ Mini App не сможет отобразить изображения
  - ❌ Веб-интерфейс не покажет медиа
  
- Рекомендуется использовать поддомен типа `cdn.quiz-code.com` или `media.quiz-code.com`

## Проверка настройки

После настройки Custom Domain проверьте:

```bash
# 1. Проверка доступности через curl
curl -I https://cdn.quiz-code.com/prod/images/test.png

# Должен вернуть HTTP 200 или 404 (если файла нет), но НЕ SSL ошибку
# Если видите SSL ошибку - проверьте настройки Custom Domain в Cloudflare Dashboard

# 2. Проверка в браузере
# Откройте в браузере: https://cdn.quiz-code.com/prod/images/test.png
# Должна загрузиться картинка или показаться 404 (но не SSL ошибка)

# 3. Проверка через Telegram Bot API (тест отправки фото)
# Используйте тестовый скрипт или отправьте фото через бота
```

## Как это работает для каждого компонента

### 1. Telegram Bot
```python
# bot/services/publication_service.py
await bot.send_photo(
    chat_id=group.group_id,
    photo=image_url,  # ← Должен быть публичный HTTPS URL
    parse_mode="MarkdownV2"
)
```
- Telegram Bot API скачивает изображение по URL
- Требуется публичный HTTPS доступ
- **Без Custom Domain не работает!**

### 2. Telegram Mini App
```html
<!-- mini_app/templates/subtopic_tasks.html -->
<img src="{{ task.image_url }}" alt="Task image" />
```
- Браузер в Telegram загружает изображение по URL
- Требуется публичный HTTPS доступ
- **Без Custom Domain не работает!**

### 3. Django Backend API
```python
# quiz_backend/tasks/serializers.py
class TaskSerializer(serializers.ModelSerializer):
    image_url = serializers.URLField()  # ← Возвращается в API ответе
```
- API возвращает URL, который используется везде
- Все компоненты используют этот URL
- **Без Custom Domain не работает!**

