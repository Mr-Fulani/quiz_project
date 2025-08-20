# Отладка кэша Telegram WebApp

## Проблема
Telegram WebApp агрессивно кэширует статические файлы (JS, CSS), что затрудняет отладку при разработке.

## Способы очистки кэша

### 1. Версионирование файлов (автоматическое)
✅ **Уже реализовано в проекте**
```html
<script src="/static/js/donation.js?v=2.1&t=1736123456"></script>
```

### 2. Принудительная очистка в Telegram
- **На мобильном**: Удалить и переустановить Telegram
- **На десктопе**: Settings → Advanced → Clear cache
- **Telegram Web**: Ctrl+Shift+R или очистка кэша браузера

### 3. Использование Telegram Bot API для очистки
```bash
# Отправить команду боту для обновления Mini App
curl -X POST "https://api.telegram.org/bot${BOT_TOKEN}/answerWebAppQuery" \
  -H "Content-Type: application/json" \
  -d '{
    "web_app_query_id": "query_id",
    "result": {
      "type": "article",
      "id": "1",
      "title": "Cache cleared",
      "message_text": "Cache has been cleared"
    }
  }'
```

### 4. Динамические timestamp в разработке
```js
// В JavaScript можно принудительно добавлять timestamp
const script = document.createElement('script');
script.src = `/static/js/myfile.js?t=${Date.now()}`;
document.head.appendChild(script);
```

### 5. Тестирование в разных окружениях
- **Локально с ngrok**: Telegram кэширует меньше
- **Режим разработки**: Используйте Telegram Web версию
- **Инкогнито/приватный режим**: Минимальное кэширование

## Рекомендации для разработки

### При каждом изменении JS/CSS:
1. **Обновить версию** в `/mini_app/utils/cache_buster.py`
2. **Проверить timestamp** добавляется автоматически  
3. **Перезапустить контейнер** мини-аппа:
   ```bash
   docker-compose restart mini_app
   ```

### Для критических изменений:
1. **Увеличить основную версию** (например, v2.1 → v2.2)
2. **Добавить новый параметр** для полной очистки:
   ```html
   <script src="/static/js/donation.js?v=2.2&cache=bust&t={{ timestamp }}"></script>
   ```

### Проверка обновления:
1. Открыть Developer Tools в браузере/Telegram Web
2. Проверить Network tab - файлы должны загружаться заново
3. Убедиться что timestamp в URL изменился

## Автоматизация

### Скрипт для автоматического обновления версий:
```bash
#!/bin/bash
# update_cache_version.sh

echo "Updating cache versions..."

# Обновляем timestamp
current_time=$(date +%s)

# Заменяем в base.html
sed -i "s/&t=[0-9]*&/&t=${current_time}&/g" mini_app/templates/base.html

# Перезапускаем контейнер
docker-compose restart mini_app

echo "Cache versions updated with timestamp: ${current_time}"
```

## В продакшене
- Версии обновляются автоматически при каждом запросе
- Timestamp генерируется динамически
- Пользователи получают обновления через 5-15 минут после деплоя
