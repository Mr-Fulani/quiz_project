# Пошаговая инструкция: Получение Pinterest токена через OAuth

## Шаг 1: Настройка Redirect URI в Pinterest Developers

1. Откройте https://developers.pinterest.com/
2. Войдите в свой аккаунт
3. Выберите ваше приложение **Quiz-Hub** (App ID: 1538458)
4. Перейдите в раздел **"URI перенаправления"** (Redirect URI)
5. Добавьте Redirect URI:
   - **Для локальной разработки:** `http://localhost:8001/auth/pinterest/callback/`
   - **Для продакшена:** `https://quiz-code.com/auth/pinterest/callback/`
6. Нажмите **"Добавить"** или **"Сохранить"**

## Шаг 2: Добавьте настройки в .env файл

1. Откройте файл `.env` в корне проекта
2. Добавьте обязательные настройки:
   ```
   PINTEREST_CLIENT_SECRET=ff674da820552c6da26d07d40846fb99c3dc4788
   PINTEREST_USE_SANDBOX=true
   ```
   Где:
   - `PINTEREST_CLIENT_SECRET` - ваш секретный ключ приложения из Pinterest Developers
   - `PINTEREST_USE_SANDBOX=true` - **обязательно** для Trial доступа (использует Sandbox API)

3. Опционально, если хотите изменить Redirect URI:
   ```
   PINTEREST_REDIRECT_URI=http://localhost:8001/auth/pinterest/callback/
   ```

**Важно:** Для Trial доступа Pinterest **обязательно** нужно использовать Sandbox API. 
Без `PINTEREST_USE_SANDBOX=true` вы получите ошибку 403 при попытке создать пин.

## Шаг 3: Запустите сервер (если еще не запущен)

```bash
docker compose up -d
```

## Шаг 4: Получите токен через OAuth

### Вариант A: Через браузер (рекомендуется)

1. Откройте в браузере:
   ```
   http://localhost:8001/auth/pinterest/authorize/
   ```
   (Для продакшена: `https://quiz-code.com/auth/pinterest/authorize/`)

2. Вас перенаправит на Pinterest для авторизации
3. Войдите в свой Pinterest аккаунт
4. Разрешите приложению доступ к:
   - Доскам (чтение и запись)
   - Пинам (чтение и запись)
   - Аккаунту (чтение)

5. После авторизации Pinterest перенаправит вас обратно
6. Токен автоматически сохранится в админке Django

### Вариант B: Через админку (если есть кнопка)

1. Откройте админку: `http://localhost:8001/admin/`
2. Перейдите: **Webhooks → Social Media Credentials**
3. Если есть запись Pinterest, откройте её
4. Нажмите кнопку **"Получить токен через OAuth"** (если реализована)
5. Или используйте прямой URL из Варианта A

## Шаг 5: Проверьте сохраненный токен

1. Откройте админку: `http://localhost:8001/admin/webhooks/socialmediacredentials/`
2. Найдите запись **Pinterest**
3. Проверьте:
   - ✅ **Access Token** заполнен
   - ✅ **Is Active** включен
   - ✅ **Token Expires At** указана дата истечения

## Шаг 6: Настройте Board ID (доску для автопостинга)

Для работы автопостинга нужно указать, на какую доску Pinterest публиковать пины.

### Вариант A: Через Django management команду (рекомендуется)

1. Выполните команду для получения списка досок:
   ```bash
   docker compose exec quiz_backend python manage.py get_pinterest_boards
   ```

2. Команда покажет список всех ваших досок с их ID

3. Если у вас только одна доска, она автоматически установится

4. Если досок несколько, скопируйте нужный `board_id` из вывода команды

### Вариант B: Вручную через админку

1. Откройте админку: `http://localhost:8001/admin/webhooks/socialmediacredentials/`
2. Найдите и откройте запись **Pinterest**
3. В поле **"Extra data"** добавьте JSON:
   ```json
   {
     "board_id": "ВАШ_BOARD_ID"
   }
   ```
   Где `ВАШ_BOARD_ID` - это ID доски из Pinterest (например: `"1234567890123456789"` или `"username/board-name"`)

4. Нажмите **"Сохранить"**

### Как узнать Board ID?

**Способ 1:** Используйте команду `get_pinterest_boards` (см. Вариант A выше)

**Способ 2:** Через Pinterest API:
- Для Trial доступа: `https://api-sandbox.pinterest.com/v5/boards`
- Для Production доступа: `https://api.pinterest.com/v5/boards`
- Используйте ваш access token в заголовке `Authorization: Bearer YOUR_TOKEN`
- В ответе будет список досок с их ID

**Способ 3:** Из URL доски в Pinterest:
- Откройте доску в Pinterest
- URL будет вида: `https://www.pinterest.com/username/board-name/`
- Board ID может быть в формате `username/board-name` или числовой ID

## Шаг 7: Протестируйте публикацию

1. Откройте админку: `http://localhost:8001/admin/tasks/task/`
2. Выберите задачу с изображением
3. Установите `published=True`
4. Сохраните
5. Проверьте логи:
   ```bash
   docker compose logs -f quiz_backend | grep -i pinterest
   ```
6. Проверьте Pinterest - пин должен появиться на доске

## Troubleshooting

### Ошибка 403: "Apps with Trial access may not create Pins in production"
**Решение:** Убедитесь, что в `.env` файле установлено:
```
PINTEREST_USE_SANDBOX=true
```
Trial доступ Pinterest требует использования Sandbox API (`api-sandbox.pinterest.com`) вместо Production API.

### Ошибка: "redirect_uri_mismatch"
- Проверьте, что Redirect URI в Pinterest Developers точно совпадает с URL в коде
- Убедитесь, что используете правильный протокол (http для localhost, https для продакшена)

### Ошибка: "invalid_client"
- Проверьте, что Client Secret правильно указан в `.env` файле
- Убедитесь, что Client ID правильный (1538458)

### Ошибка: "invalid_grant"
- Authorization code истек (действует 10 минут)
- Попробуйте снова: откройте `/auth/pinterest/authorize/`

### Токен не сохраняется
- Проверьте логи Django:
  ```bash
  docker compose logs -f quiz_backend
  ```
- Убедитесь, что база данных доступна
- Проверьте права доступа к файлу `.env`

## Что дальше?

После успешного получения токена:
- ✅ Автопостинг будет работать при публикации задач
- ✅ Токен автоматически сохранится в админке
- ✅ При истечении токена нужно будет повторить OAuth flow

## Примечания

- **Trial токены** действуют ограниченное время (обычно 24 часа)
- Для **production** нужен постоянный токен через OAuth
- **Refresh token** можно использовать для обновления access token (если реализовано)

