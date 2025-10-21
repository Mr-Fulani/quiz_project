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
Добавлены недостающие маршруты для мини-аппа (аналогично локальной конфигурации).

### 2. Улучшена обработка ошибок в `quiz_backend/blog/views.py`
Форма обратной связи теперь сохраняет сообщения в БД, даже если отправка email не удалась.

## Деплой на продакшен

### Шаг 1: Проверить переменную окружения
На продакшен сервере убедитесь, что в `.env` файле есть:
```bash
ADMIN_TELEGRAM_ID=your_telegram_username  # без символа @
```

Например:
```bash
ADMIN_TELEGRAM_ID=mr_fulani
```

### Шаг 2: Загрузить изменения на сервер
```bash
# На локальной машине:
git add .
git commit -m "Fix feedback and contact admin buttons on production"
git push origin main
```

### Шаг 3: Обновить код на сервере
```bash
# На продакшен сервере:
cd /opt/quiz_project/quiz_project  # или ваш путь
git pull origin main
```

### Шаг 4: Пересобрать и перезапустить контейнеры
```bash
# Останавливаем контейнеры
docker compose down

# Пересобираем nginx с новой конфигурацией
docker compose build nginx

# Запускаем все контейнеры
docker compose up -d
```

### Шаг 5: Проверить логи
```bash
# Проверяем, что nginx запустился корректно
docker compose logs nginx --tail=50

# Проверяем mini_app
docker compose logs mini_app --tail=50

# Проверяем, что ADMIN_TELEGRAM_ID передался
docker compose exec mini_app env | grep ADMIN_TELEGRAM_ID
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

