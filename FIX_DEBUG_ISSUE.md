# 🚨 ИСПРАВЛЕНИЕ ПРОБЛЕМЫ DEBUG=True

## 🔍 Проблема

В продакшен-окружении (`docker-compose.local-prod.yml`) Django запускается с `DEBUG=True` вместо `DEBUG=False`, из-за чего:

1. ❌ Версионирование статических файлов (`ManifestStaticFilesStorage`) **не работает**
2. ❌ Манифест `staticfiles.json` **не создается**
3. ❌ CSS файлы **не получают хеши** в именах
4. ❌ Браузеры **кешируют старые стили**

## 💡 Причина

Файл `.env` загружается **ДО** явного указания переменных окружения в `docker-compose.local-prod.yml`, поэтому значение `DEBUG=True` из `.env` переопределяет `DEBUG=False` из docker-compose.

## ✅ Решение

Удалены строки `env_file: - .env` из `docker-compose.local-prod.yml` для секций:
- `quiz_backend`
- `mini_app`
- `telegram_bot`

Теперь явно указанные переменные окружения имеют приоритет.

## 🚀 Применение исправления

### На локальной машине:

```bash
# 1. Закоммитить изменения
git add docker-compose.local-prod.yml
git commit -m "fix: удалить env_file для корректной работы DEBUG=False в продакшене"
git push origin main
```

### На удаленном сервере:

```bash
# 1. Получить изменения
cd /opt/quiz_project/quiz_project
git pull origin main

# 2. Перезапустить с новыми настройками
./start-prod.sh
```

## 🔍 Проверка результата

### 1. Проверьте, что DEBUG=False:

```bash
docker compose -f docker-compose.local-prod.yml exec quiz_backend python -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.conf import settings
print(f'DEBUG: {settings.DEBUG}')
print(f'STORAGES: {settings.STORAGES}')
"
```

**Ожидаемый результат:**
```
DEBUG: False
STORAGES: {'default': {...}, 'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'}}
```

### 2. Проверьте наличие манифеста:

```bash
docker compose -f docker-compose.local-prod.yml exec quiz_backend ls -la staticfiles/staticfiles.json
```

**Ожидаемый результат:**
```
-rw-r--r-- 1 root root XXXXX Oct 11 XX:XX staticfiles/staticfiles.json
```

### 3. Проверьте версионированные CSS файлы:

```bash
docker compose -f docker-compose.local-prod.yml exec quiz_backend find staticfiles -name "*.css" | head -5
```

**Ожидаемый результат:**
```
staticfiles/blog/css/global.abc123def.css
staticfiles/blog/css/quiz_styles.456789ghi.css
...
```

## 🌐 В браузере:

1. Откройте DevTools (F12)
2. Перейдите на вкладку Network
3. Включите "Disable cache"
4. Выполните жесткую перезагрузку: `Ctrl+Shift+R` (Windows/Linux) или `Cmd+Shift+R` (macOS)
5. Проверьте, что CSS файлы содержат хеш в имени

## ✅ Ожидаемый результат

После применения исправления:

✅ `DEBUG = False` в продакшене
✅ Манифест `staticfiles.json` создается
✅ CSS файлы имеют хеши в именах (cache busting)
✅ Стили на локальной машине и сервере **идентичны**

---

**Дата:** 11 октября 2025
**Версия исправления:** 1.0

