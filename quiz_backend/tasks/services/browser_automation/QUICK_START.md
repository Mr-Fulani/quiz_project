# Быстрый старт: Браузерная автоматизация для Instagram Reels

## ✅ Проверка миграций

```bash
cd quiz_backend
python manage.py showmigrations webhooks tasks
```

Если видите `[ ]` (не применено) перед миграциями:
```bash
python manage.py migrate webhooks
python manage.py migrate tasks
```

## ⚙️ Настройки в settings.py

Настройки **уже добавлены** в `settings.py`:

```python
# Browser Automation Settings
BROWSER_AUTOMATION_ENABLED = True
BROWSER_HEADLESS = True  # False для отладки
BROWSER_TIMEOUT = 60
BROWSER_RETRY_COUNT = 3
```

Можно переопределить через `.env`:
```env
BROWSER_AUTOMATION_ENABLED=true
BROWSER_HEADLESS=false  # false для первого запуска
BROWSER_TIMEOUT=60
BROWSER_RETRY_COUNT=3
```

## 🔐 Где вписывать логин и пароль от Instagram?

**Важно:** Логин и пароль **НЕ ВПИСЫВАЮТСЯ** нигде!

Вместо этого:

1. **Откройте Django Admin**: `/admin/webhooks/socialmediacredentials/add/`

2. **Создайте новую запись**:
   - **Platform**: выберите `Instagram`
   - **Access Token**: можно оставить пустым (не используется для браузерной автоматизации)
   - **Browser Type**: `Playwright` (рекомендуется)
   - **Headless Mode**: 
     - `False` для первого раза (чтобы видеть браузер)
     - `True` для продакшена
   - **Is Active**: `True`

3. **Сохраните**

4. **При первом запуске публикации**:
   - Откроется браузер (если headless=False)
   - Вы вручную войдете в Instagram
   - Сессия (cookies) автоматически сохранится
   - В следующих запусках авторизация не потребуется

## 🧪 Как тестировать?

### Вариант 1: Через Django Admin (проще)

1. Установите Playwright браузеры:
   ```bash
   playwright install chromium
   ```

2. Создайте credentials (см. выше)

3. Перейдите в `/admin/tasks/task/`

4. Выберите задачу **с видео** (`video_url` должен быть заполнен)

5. Выберите действие: **"🎥 Опубликовать в Instagram Reels"**

6. Нажмите "Выполнить"

7. При первом запуске войдите в Instagram в открывшемся браузере

### Вариант 2: Через тестовый скрипт

```bash
cd quiz_backend
python tasks/services/browser_automation/test_instagram_reels.py
```

Скрипт проверит:
- Наличие credentials
- Наличие задачи с видео
- Выполнит публикацию

### Вариант 3: Программно

```python
from tasks.models import Task, TaskTranslation
from tasks.services.social_media_service import publish_to_platform

task = Task.objects.get(id=123)  # Замените на ID вашей задачи
translation = task.translations.first()

result = publish_to_platform(task, translation, 'instagram_reels')
print(result)
```

## 📋 Чек-лист перед тестированием

- [ ] Миграции применены
- [ ] Playwright браузеры установлены: `playwright install chromium`
- [ ] Создан `SocialMediaCredentials` для Instagram в админке
- [ ] У задачи есть `video_url` (публично доступный URL)
- [ ] У задачи есть переводы
- [ ] `headless_mode = False` для первого теста (чтобы видеть процесс)

## 🔍 Проверка статуса

### Проверить credentials:
```python
from webhooks.models import SocialMediaCredentials

creds = SocialMediaCredentials.objects.get(platform='instagram')
print(f"Browser Type: {creds.browser_type}")
print(f"Headless: {creds.headless_mode}")
print(f"Active: {creds.is_active}")
```

### Проверить сохраненную сессию:
```python
session = creds.extra_data.get('browser_session')
if session:
    print(f"Сессия сохранена: {session.get('saved_at')}")
    print(f"Cookies: {len(session.get('cookies', []))} шт.")
else:
    print("Сессия не найдена - потребуется авторизация")
```

## 📚 Полная документация

См. `TESTING_GUIDE.md` для детальной информации и решения проблем.

