# 🎨 Проблема с кэшированием статических файлов

## 📋 Описание проблемы

При работе с приложением вы могли заметить, что **стили на локальной машине и на удаленном сервере отличаются**. После выполнения `git pull` новые стили не применяются сразу.

### Причины:

1. **Кэширование в Nginx** - в продакшен-конфигурации настроено долгосрочное кэширование статических файлов (`expires 30d`)
2. **Кэширование в браузере** - браузер сохраняет статические файлы на диск
3. **Отсутствие версионирования файлов** - файлы имеют одинаковые имена, поэтому браузер не знает, что они обновились

---

## ✅ Примененные решения

### 1. Версионирование файлов через ManifestStaticFilesStorage

В `quiz_backend/config/settings.py` изменено:

```python
# Было:
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

# Стало:
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'
```

**Что это дает:**
- Django добавляет хеш к именам файлов (например, `style.css` → `style.abc123.css`)
- При изменении файла меняется его хеш, поэтому браузер загружает новую версию
- Можно безопасно кэшировать файлы на долгий срок

### 2. Оптимизация кэширования в Nginx

В `nginx/nginx-prod.conf` обновлена конфигурация:

```nginx
location /static/ {
    alias /app/staticfiles/;
    
    # Файлы с хешами (версионированные) кэшируем на год
    location ~ \.(css|js|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
        access_log off;
    }
    
    # Остальные статические файлы кэшируем на 1 день
    expires 1d;
    add_header Cache-Control "public, must-revalidate";
}
```

**Что это дает:**
- Версионированные файлы (с хешами) кэшируются на 1 год - это безопасно, т.к. при изменении меняется имя файла
- Остальные файлы кэшируются на 1 день с проверкой актуальности
- Снижается нагрузка на сервер и ускоряется загрузка сайта

---

## 🚀 Как применить изменения

### После обновления кода (git pull):

1. **Запустите скрипт очистки кэша:**
   ```bash
   ./clear_cache.sh
   ```
   
   Этот скрипт:
   - Очищает папку `staticfiles/` в контейнере
   - Пересобирает статические файлы с новыми хешами
   - Перезапускает Nginx

2. **Очистите кэш в браузере:**
   - **Windows/Linux:** `Ctrl + Shift + R`
   - **macOS:** `Cmd + Shift + R`

### Альтернативный способ (полная пересборка):

```bash
# Для продакшена
docker compose -f docker-compose.local-prod.yml down
docker compose -f docker-compose.local-prod.yml up -d --build

# Для локальной разработки
docker compose down
docker compose up -d --build
```

---

## 🔧 Отладка проблем со статикой

### Проверка, что статика собралась:

```bash
# Для продакшена
docker compose -f docker-compose.local-prod.yml exec quiz_backend ls -la staticfiles/

# Для локальной разработки
docker compose exec quiz_backend ls -la staticfiles/
```

### Проверка версионирования файлов:

Посмотрите на имена файлов в `staticfiles/`. Они должны содержать хеш:
```
admin/css/base.abc123def456.css
admin/js/vendor.789xyz012.js
```

### Проверка заголовков кэширования:

Откройте DevTools (F12) → вкладка Network → обновите страницу → кликните на CSS файл → посмотрите Headers:

```
Cache-Control: public, immutable
Expires: (дата через год)
```

### Если стили все еще не обновляются:

1. **Откройте DevTools (F12)**
2. Перейдите на вкладку **Network**
3. Включите **"Disable cache"**
4. Перезагрузите страницу с **Ctrl+Shift+R** (или **Cmd+Shift+R**)

---

## 📝 Дополнительные рекомендации

### Для разработки (DEBUG=True):

- Кэширование отключено автоматически
- Django отдает статические файлы напрямую
- Изменения применяются сразу

### Для продакшена (DEBUG=False):

- **Всегда запускайте `./clear_cache.sh` после обновления кода**
- Используйте версионирование файлов (уже настроено)
- Nginx отдает статику напрямую из `staticfiles/`
- Gunicorn не участвует в раздаче статики

---

## 🆘 Частые проблемы

### Проблема: "Ошибка при сборке статики"

**Решение:**
```bash
docker compose -f docker-compose.local-prod.yml exec quiz_backend python manage.py collectstatic --noinput --clear -v 2
```

Флаг `-v 2` покажет подробную информацию о процессе сборки.

### Проблема: "Статика не загружается (404)"

**Проверьте:**
1. Собраны ли статические файлы: `docker compose exec quiz_backend ls staticfiles/`
2. Правильные ли права доступа: `docker compose exec quiz_backend ls -la staticfiles/`
3. Правильная ли конфигурация Nginx: `docker compose exec nginx cat /etc/nginx/nginx.conf`

### Проблема: "Старые стили все еще отображаются"

**Решение:**
1. Запустите `./clear_cache.sh`
2. Очистите кэш браузера (Ctrl+Shift+R)
3. Попробуйте режим инкогнито
4. Проверьте, что манифест обновился: `docker compose exec quiz_backend cat staticfiles/staticfiles.json`

---

## 📚 Полезные ссылки

- [Django Static Files](https://docs.djangoproject.com/en/stable/howto/static-files/)
- [ManifestStaticFilesStorage](https://docs.djangoproject.com/en/stable/ref/contrib/staticfiles/#manifeststaticfilesstorage)
- [Nginx Caching](https://nginx.org/en/docs/http/ngx_http_headers_module.html#expires)
- [HTTP Caching Best Practices](https://developer.mozilla.org/en-US/docs/Web/HTTP/Caching)

