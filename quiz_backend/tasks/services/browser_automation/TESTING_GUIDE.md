# Руководство по тестированию браузерной автоматизации

## Проверка миграций

### 1. Проверка статуса миграций

```bash
cd quiz_backend
python manage.py showmigrations webhooks
python manage.py showmigrations tasks
```

### 2. Применение миграций (если не применены)

```bash
python manage.py migrate webhooks
python manage.py migrate tasks
```

### 3. Проверка создания таблиц

```bash
python manage.py dbshell
```

В psql выполните:
```sql
-- Проверить, что поля добавлены в social_media_credentials
\d webhooks_socialmediacredentials

-- Проверить, что платформы обновлены в social_media_posts
\d tasks_social_media_posts
```

## Настройка credentials для Instagram

### Важно!
Для Instagram **НЕ НУЖЕН** access_token. Авторизация происходит через браузер.

### Шаги настройки:

1. **Откройте Django Admin**: `/admin/webhooks/socialmediacredentials/`

2. **Добавьте новую запись**:
   - **Platform**: `Instagram`
   - **Access Token**: можно оставить пустым или заполнить любым значением (не используется)
   - **Browser Type**: `Playwright` (рекомендуется) или `Selenium`
   - **Headless Mode**: 
     - `False` для первого раза (чтобы видеть процесс авторизации)
     - `True` для продакшена
   - **Is Active**: `True`

3. **Сохраните**

## Тестирование Instagram Reels

### 1. Подготовка

Убедитесь, что:
- Задача имеет `video_url` (URL видео файла)
- Задача имеет переводы
- Playwright браузеры установлены: `playwright install chromium`

### 2. Тест через Django Admin

1. Перейдите в `/admin/tasks/task/`
2. Выберите задачу с видео
3. Выберите действие **"🎥 Опубликовать в Instagram Reels"**
4. Нажмите "Выполнить"

### 3. Первая авторизация

При первом запуске:
- Если `headless_mode = False`, откроется браузер
- Войдите в Instagram вручную
- После успешной авторизации сессия сохранится автоматически
- В следующих запусках авторизация не потребуется

### 4. Тест через код

```python
from tasks.models import Task, TaskTranslation
from tasks.services.social_media_service import publish_to_platform

# Получаем задачу с видео
task = Task.objects.get(id=123)  # Замените на ID вашей задачи
translation = task.translations.first()

# Публикуем в Instagram Reels
result = publish_to_platform(task, translation, 'instagram_reels')

print(result)
# {
#     'platform': 'instagram_reels',
#     'success': True/False,
#     'post_id': '...',
#     'post_url': 'https://www.instagram.com/reel/...',
#     'facebook_post_id': '...' (если кросспостинг включен),
#     'instagram_story_id': '...' (если добавлено в Stories),
#     'error': '...' (если success=False)
# }
```

### 5. Тест с автоматическим репостом

```python
# Через админку: действие "🚀 Опубликовать Reels с автоматическим репостом"
# Или программно:
result = publish_to_platform(task, translation, 'instagram_reels')
# Кросспостинг в Facebook и добавление в Stories произойдет автоматически
# если аккаунты Instagram-Facebook связаны
```

## Проверка настроек в settings.py

Убедитесь, что в `settings.py` есть следующие настройки:

```python
# Browser Automation Settings
BROWSER_AUTOMATION_ENABLED = True  # Включить браузерную автоматизацию
BROWSER_HEADLESS = True  # Headless режим (False для отладки)
BROWSER_TIMEOUT = 60  # Таймаут операций в секундах
BROWSER_RETRY_COUNT = 3  # Количество повторных попыток
```

Или через переменные окружения в `.env`:

```env
BROWSER_AUTOMATION_ENABLED=true
BROWSER_HEADLESS=false  # false для отладки
BROWSER_TIMEOUT=60
BROWSER_RETRY_COUNT=3
```

## Проверка связи аккаунтов Instagram-Facebook

Для использования кросспостинга:

1. Откройте Instagram в браузере
2. Перейдите в **Настройки** → **Аккаунт** → **Связанные аккаунты**
3. Свяжите Instagram с Facebook страницей
4. Убедитесь, что Instagram аккаунт преобразован в **бизнес-профиль**

После этого при публикации Reels будет доступен чекбокс "Также делиться в Facebook".

## Отладка

### Логи

Все действия логируются. Проверьте логи:

```python
import logging
logging.getLogger('tasks.services.browser_automation').setLevel(logging.DEBUG)
```

### Headless режим

Для отладки установите `headless_mode = False` в credentials, чтобы видеть действия браузера.

### Проверка сессии

Сессия сохраняется в `SocialMediaCredentials.extra_data['browser_session']`. Проверить можно через:

```python
from webhooks.models import SocialMediaCredentials

creds = SocialMediaCredentials.objects.get(platform='instagram')
session = creds.extra_data.get('browser_session')
if session:
    print(f"Сессия сохранена: {session.get('saved_at')}")
    print(f"Cookies: {len(session.get('cookies', []))} шт.")
```

### Очистка сессии

Если нужно переавторизоваться:

```python
from webhooks.models import SocialMediaCredentials
from tasks.services.browser_automation.session_manager import BrowserSessionManager

creds = SocialMediaCredentials.objects.get(platform='instagram')
BrowserSessionManager.clear_session(creds)
```

## Частые проблемы

### 1. "Не удалось запустить браузер"

**Решение**: Установите браузеры Playwright:
```bash
playwright install chromium
```

### 2. "Ошибка авторизации"

**Решение**: 
- Установите `headless_mode = False` для первой авторизации
- Войдите в Instagram вручную в открывшемся браузере
- Сессия сохранится автоматически

### 3. "Аккаунты Instagram-Facebook не связаны"

**Решение**: Свяжите аккаунты через настройки Instagram (см. выше)

### 4. "Не удалось загрузить видео"

**Решение**:
- Убедитесь, что `task.video_url` содержит валидный URL
- URL должен быть публично доступен
- Проверьте формат видео (должен быть MP4)

### 5. Миграции не применяются

**Решение**:
```bash
# Проверьте статус
python manage.py showmigrations webhooks tasks

# Примените вручную
python manage.py migrate webhooks 0004_add_browser_automation_fields
python manage.py migrate tasks 0012_update_social_media_post_platforms
```

## Тестовый скрипт

Создайте файл `test_instagram_reels.py`:

```python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from tasks.models import Task, TaskTranslation
from tasks.services.social_media_service import publish_to_platform
from webhooks.models import SocialMediaCredentials

# Проверка credentials
creds = SocialMediaCredentials.objects.filter(platform='instagram', is_active=True).first()
if not creds:
    print("❌ Не найдены credentials для Instagram")
    print("Создайте их через Django Admin: /admin/webhooks/socialmediacredentials/add/")
    exit(1)

print(f"✅ Credentials найдены: {creds.platform}, browser_type={creds.browser_type}")

# Получение задачи с видео
task = Task.objects.filter(video_url__isnull=False).first()
if not task:
    print("❌ Не найдена задача с видео")
    exit(1)

print(f"✅ Задача найдена: ID={task.id}, video_url={task.video_url}")

translation = task.translations.first()
if not translation:
    print("❌ У задачи нет переводов")
    exit(1)

print(f"✅ Перевод найден: язык={translation.language}")

# Тест публикации
print("\n🚀 Начинаем публикацию...")
result = publish_to_platform(task, translation, 'instagram_reels')

if result.get('success'):
    print(f"✅ Успешно! Post ID: {result.get('post_id')}")
    print(f"   URL: {result.get('post_url')}")
    if result.get('facebook_post_id'):
        print(f"   Facebook Reels: {result.get('facebook_post_id')}")
    if result.get('instagram_story_id'):
        print(f"   Instagram Story: {result.get('instagram_story_id')}")
else:
    print(f"❌ Ошибка: {result.get('error')}")
```

Запуск:
```bash
cd quiz_backend
python test_instagram_reels.py
```

