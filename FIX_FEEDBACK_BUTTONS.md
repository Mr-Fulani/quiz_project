# Исправление кнопок обратной связи на продакшене

## Проблема
Кнопки обратной связи и "Написать админу" не работают на продакшене, но работают локально.

## Причина
В продакшн конфигурации nginx отсутствовали маршруты для API эндпоинтов мини-аппа:
- `/api/feedback/` 
- `/api/admin-analytics/`
- `/api/get-config/`

Также могла отсутствовать переменная окружения `ADMIN_TELEGRAM_ID`.

## Исправления

### 1. Обновлен `nginx/nginx-prod.conf`
Добавлены недостающие маршруты для мини-аппа (аналогично локальной конфигурации):
- `/api/feedback/` → mini_app
- `/api/admin-analytics/` → mini_app  
- `/api/get-config/` → mini_app

### 2. Улучшена обработка ошибок в `quiz_backend/blog/views.py`
Форма обратной связи теперь сохраняет сообщения в БД, даже если отправка email не удалась.

### 3. Обновлен `mini_app/core/config.py`
- Добавлено логирование загрузки переменных окружения
- Улучшена загрузка `ADMIN_TELEGRAM_ID` из Docker environment

### 4. Улучшен `mini_app/static/js/feedback.js`
- Функция `contactAdmin()` теперь асинхронная
- Автоматически загружает `ADMIN_TELEGRAM_ID` из API, если он не установлен
- Более подробное логирование для отладки

## Деплой на продакшен

### Вариант 1: Автоматический деплой (Рекомендуется)

```bash
# На локальной машине:
git add .
git commit -m "Fix feedback and contact admin buttons on production"
git push origin main

# На продакшен сервере:
cd /opt/quiz_project/quiz_project
git pull origin main

# Запускаем скрипт автоматического деплоя
./deploy_feedback_fix.sh
```

Скрипт автоматически:
- ✅ Проверит наличие `ADMIN_TELEGRAM_ID` в `.env`
- ✅ Проверит наличие исправлений в `nginx-prod.conf`
- ✅ Пересоберет nginx и mini_app
- ✅ Перезапустит контейнеры
- ✅ Проверит загрузку переменных
- ✅ Протестирует API `/api/get-config/`

### Вариант 2: Ручной деплой

#### Шаг 1: Проверить переменную окружения
На продакшен сервере убедитесь, что в `.env` файле есть:
```bash
ADMIN_TELEGRAM_ID=your_telegram_username  # без символа @
```

Проверка:
```bash
cat .env | grep ADMIN_TELEGRAM_ID
# Должно быть: ADMIN_TELEGRAM_ID=Mr_Fulani
```

#### Шаг 2: Загрузить изменения на сервер
```bash
# На локальной машине:
git add .
git commit -m "Fix feedback and contact admin buttons on production"
git push origin main
```

#### Шаг 3: Обновить код на сервере
```bash
# На продакшен сервере:
cd /opt/quiz_project/quiz_project
git pull origin main

# Проверяем, что изменения попали в nginx-prod.conf
grep "api/get-config/" nginx/nginx-prod.conf
grep "api/feedback/" nginx/nginx-prod.conf
# Обе команды должны найти совпадения
```

#### Шаг 4: Пересобрать и перезапустить контейнеры
```bash
# Останавливаем контейнеры
docker compose down

# Пересобираем nginx и mini_app с новой конфигурацией
docker compose build nginx mini_app

# Запускаем все контейнеры
docker compose up -d
```

#### Шаг 5: Проверить логи и переменные
```bash
# Ждем запуска контейнеров
sleep 10

# Проверяем логи mini_app
docker compose logs mini_app | grep "ADMIN_TELEGRAM_ID"
# Должно быть: ✅ Settings loaded: ADMIN_TELEGRAM_ID=[Mr_Fulani]

# Проверяем статус контейнеров
docker compose ps

# Тестируем API
curl http://localhost/api/get-config/
# Должен вернуть: {"admin_telegram_id":"Mr_Fulani"}
```

## Проверка работы

### 1. Кнопка обратной связи в мини-аппе
1. Откройте мини-апп (mini.quiz-code.com)
2. Перейдите в Settings (Настройки)
3. Прокрутите до раздела "Обратная связь"
4. Выберите категорию (Баг/Предложение/Жалоба/Другое)
5. Введите сообщение
6. Нажмите "Отправить"
7. Должно появиться "Спасибо! Ваше сообщение отправлено"

### 2. Кнопка "Написать админу"
1. В том же разделе "Обратная связь"
2. Нажмите кнопку "Написать админу" (с иконкой конверта)
3. Должен открыться чат с админом в Telegram

### 3. Форма обратной связи на сайте
1. Откройте quiz-code.com/contact/
2. Заполните форму (имя, email, сообщение)
3. Нажмите "Send Message"
4. Должно появиться "Message sent!"

## Отладка

Если проблемы остались:

### 1. Проверить логи в реальном времени
```bash
# Логи nginx
docker compose logs nginx -f

# Логи mini_app
docker compose logs mini_app -f

# Логи quiz_backend
docker compose logs quiz_backend -f
```

### 2. Проверить маршруты nginx
```bash
docker compose exec nginx cat /etc/nginx/nginx.conf | grep -A 10 "api/feedback"
```

### 3. Проверить переменные окружения
```bash
# В mini_app
docker compose exec mini_app env | grep ADMIN_TELEGRAM_ID

# В quiz_backend
docker compose exec quiz_backend env | grep EMAIL
```

### 4. Тест запроса к API
```bash
# С сервера:
curl -X POST https://mini.quiz-code.com/api/feedback/ \
  -H "Content-Type: application/json" \
  -d '{"telegram_id": 123456, "username": "test", "message": "test message", "category": "other"}'

# Проверка get-config:
curl https://mini.quiz-code.com/api/get-config/
# Должен вернуть: {"admin_telegram_id":"Mr_Fulani"}
```

### 5. Проверка логов mini_app
```bash
# Смотрим логи при запуске mini_app
docker compose logs mini_app | grep "ADMIN_TELEGRAM_ID"

# Должно быть:
# ✅ Settings loaded: ADMIN_TELEGRAM_ID=[Mr_Fulani]
```

### 6. Проверка в браузере (Developer Console)
Откройте Developer Tools (F12) и перейдите в Console:
```javascript
// Проверяем, загружен ли ADMIN_TELEGRAM_ID
console.log(window.ADMIN_TELEGRAM_ID);

// Проверяем API напрямую
fetch('/api/get-config/')
  .then(r => r.json())
  .then(d => console.log('Config:', d));
```

## Примечания

1. **Кэширование**: После обновления nginx может потребоваться очистить кэш браузера (Ctrl+Shift+R)
2. **Email**: Если форма на сайте не отправляет email, проверьте настройки EMAIL_* в `.env` файле
3. **CSRF**: Убедитесь, что ваш домен добавлен в `CSRF_TRUSTED_ORIGINS` в `quiz_backend/config/settings.py`

## Контрольный список

- [ ] Проверен `.env` файл на наличие `ADMIN_TELEGRAM_ID`
- [ ] Код загружен на сервер через `git pull`
- [ ] Nginx пересобран с новой конфигурацией
- [ ] Контейнеры перезапущены
- [ ] Проверена работа кнопки обратной связи
- [ ] Проверена работа кнопки "Написать админу"
- [ ] Проверена форма обратной связи на сайте
- [ ] Логи не показывают ошибок

