# Исправление авторизации через Telegram

## Проблема
Не работает авторизация/регистрация через Telegram на сайте Django.

## Внесенные исправления

### 1. Обработка данных от QueryDict
- Исправлена обработка данных от `request.GET` и `request.POST`
- QueryDict возвращает списки, теперь правильно извлекаются первые значения
- Добавлена обработка пустых списков и None значений

### 2. Проверка подписи Telegram
- Улучшена проверка подписи с детальным логированием
- Добавлены проверки на наличие обязательных полей (hash, auth_date)
- Улучшена обработка данных для создания check_string
- Добавлено логирование computed и received hash для диагностики

### 3. Обработка данных пользователя
- Добавлены проверки на корректность telegram_id
- Улучшена обработка пустых значений username, first_name, last_name
- Добавлена защита от бесконечного цикла при генерации уникального username
- Улучшено логирование процесса создания/поиска пользователя

### 4. Обработка ошибок
- Добавлено детальное логирование во всех критических точках
- Улучшена обработка исключений с traceback
- Добавлено логирование referer и user agent для диагностики

## Команды для проверки на сервере

### 1. Проверить логи контейнера quiz_backend
```bash
docker compose -f docker-compose.local-prod.yml logs quiz_backend --tail=100 | grep -i "telegram\|auth"
```

### 2. Проверить последние логи с ошибками
```bash
docker compose -f docker-compose.local-prod.yml logs quiz_backend --tail=200 | grep -A 5 -B 5 "ERROR\|WARNING" | grep -i "telegram"
```

### 3. Проверить логи в реальном времени
```bash
docker compose -f docker-compose.local-prod.yml logs -f quiz_backend | grep -i "telegram"
```

### 4. Проверить настройки бота
```bash
# Проверить что TELEGRAM_BOT_TOKEN установлен
docker compose -f docker-compose.local-prod.yml exec quiz_backend env | grep TELEGRAM
```

### 5. Проверить доступность endpoint
```bash
# Проверить что endpoint доступен
curl -v "https://quiz-code.com/api/social-auth/telegram/auth/"
```

## Возможные причины проблем

1. **Домен не настроен в BotFather**
   - Выполните в @BotFather: `/setdomain`
   - Укажите домен: `quiz-code.com` (без протокола)

2. **Неверный TELEGRAM_BOT_TOKEN**
   - Проверьте что токен правильный в .env файле
   - Убедитесь что токен соответствует боту в BotFather

3. **Проблемы с сессией**
   - Проверьте настройки SESSION_ENGINE
   - Убедитесь что Redis работает корректно

4. **Данные не приходят от Telegram**
   - Проверьте логи на наличие "НЕТ ДАННЫХ ОТ TELEGRAM ВИДЖЕТА"
   - Убедитесь что домен правильно настроен в BotFather

## Применение исправлений

1. Переключиться на новую ветку:
```bash
git checkout fix/telegram-auth-issue
```

2. Запушить ветку на сервер:
```bash
git push origin fix/telegram-auth-issue
```

3. На сервере переключиться на ветку и пересобрать контейнеры:
```bash
cd /opt/quiz_project/quiz_project
git fetch origin
git checkout fix/telegram-auth-issue
docker compose -f docker-compose.local-prod.yml up -d --build quiz_backend
```

4. Проверить логи после перезапуска:
```bash
docker compose -f docker-compose.local-prod.yml logs -f quiz_backend | grep -i "telegram"
```

## Тестирование

После применения исправлений попробуйте авторизоваться через Telegram и проверьте логи на наличие:
- "TELEGRAM AUTH GET REQUEST" или "TELEGRAM AUTH POST REQUEST"
- "Проверка подписи Telegram"
- "Подпись Telegram успешно проверена" или "Неверная подпись"
- "Авторизация успешна" или сообщения об ошибках

