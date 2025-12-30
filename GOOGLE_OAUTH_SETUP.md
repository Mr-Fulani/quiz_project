# Настройка Google OAuth для авторизации

## Шаг 1: Создание проекта в Google Cloud Console

1. Перейдите на [Google Cloud Console](https://console.cloud.google.com/)
2. Войдите в свой Google аккаунт
3. Создайте новый проект или выберите существующий:
   - Нажмите на выпадающий список проектов вверху
   - Нажмите "New Project"
   - Введите название проекта (например, "Quiz Code OAuth")
   - Нажмите "Create"

## Шаг 2: Настройка OAuth Consent Screen

1. В меню слева перейдите в **APIs & Services** → **OAuth consent screen**
2. Выберите тип пользователей:
   - **External** (для публичного использования) ← **ВЫБЕРИТЕ ЭТО** для публичного сайта
   - **Internal** (только для пользователей вашей организации G Suite) - только для корпоративных приложений
3. Заполните обязательные поля:
   - **App name**: Quiz Code (или любое другое название)
   - **User support email**: ваш email
   - **Developer contact information**: ваш email
4. Нажмите "Save and Continue"
5. На шаге "Scopes" нажмите "Save and Continue" (можно пропустить)
6. На шаге "Test users" (если выбрали External) добавьте тестовых пользователей или нажмите "Save and Continue"
7. На шаге "Summary" проверьте информацию и нажмите "Back to Dashboard"

## Шаг 3: Создание OAuth 2.0 Client ID

1. Перейдите в **APIs & Services** → **Credentials**
2. Нажмите **"+ CREATE CREDENTIALS"** → **"OAuth client ID"**
3. Выберите **Application type**: **Web application**
4. Введите **Name**: "Quiz Code OAuth" (или любое другое название)
5. В разделе **Authorized redirect URIs** добавьте следующие URL:

   **Для продакшена:**
   ```
   https://quiz-code.com/api/social-auth/google/callback
   ```

   **Для локальной разработки (опционально):**
   ```
   http://localhost:8000/api/social-auth/google/callback
   http://127.0.0.1:8000/api/social-auth/google/callback
   ```

6. Нажмите **"Create"**

## Шаг 4: Получение Client ID и Client Secret

После создания OAuth Client ID вы увидите модальное окно с:
- **Your Client ID** (например: `123456789-abcdefghijklmnop.apps.googleusercontent.com`)
- **Your Client secret** (например: `GOCSPX-abcdefghijklmnopqrstuvwxyz`)

⚠️ **ВАЖНО**: Сохраните эти значения в безопасном месте! Client Secret показывается только один раз.

Если вы случайно закрыли окно:
1. Перейдите в **APIs & Services** → **Credentials**
2. Найдите созданный OAuth 2.0 Client ID
3. Нажмите на него
4. Client ID будет виден, но Client Secret нужно будет создать заново (нажмите "Reset secret")

## Шаг 5: Добавление переменных в проект

### Вариант 1: Добавление в .env файл

Добавьте следующие строки в ваш `.env` файл (в корне проекта или в `quiz_backend/`):

```env
# Google OAuth Settings
GOOGLE_CLIENT_ID=ваш_client_id_здесь.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=ваш_client_secret_здесь
```

**Пример:**
```env
GOOGLE_CLIENT_ID=123456789-abcdefghijklmnop.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-abcdefghijklmnopqrstuvwxyz
```

### Вариант 2: Добавление в Docker Compose

Если вы используете Docker, добавьте переменные в `docker-compose.yml`:

```yaml
services:
  quiz_backend:
    environment:
      - GOOGLE_CLIENT_ID=ваш_client_id_здесь.apps.googleusercontent.com
      - GOOGLE_CLIENT_SECRET=ваш_client_secret_здесь
```

### Вариант 3: Добавление на сервере (для продакшена)

Если вы используете системные переменные окружения или панель управления сервером:

```bash
export GOOGLE_CLIENT_ID="ваш_client_id_здесь.apps.googleusercontent.com"
export GOOGLE_CLIENT_SECRET="ваш_client_secret_здесь"
```

## Шаг 6: Перезапуск приложения

После добавления переменных окружения перезапустите приложение:

**Для Docker:**
```bash
docker compose restart quiz_backend
```

**Для локальной разработки:**
```bash
# Остановите сервер (Ctrl+C) и запустите снова
python manage.py runserver
```

## Проверка работы

1. Откройте сайт и нажмите на кнопку "Login with Google"
2. Вы должны быть перенаправлены на страницу авторизации Google
3. После авторизации вы вернетесь на сайт и будете авторизованы

## Важные замечания

1. **Redirect URI должен точно совпадать** с тем, что указан в Google Cloud Console
2. **Для продакшена** используйте HTTPS URL: `https://quiz-code.com/api/social-auth/google/callback`
3. **Для локальной разработки** можно использовать HTTP: `http://localhost:8000/api/social-auth/google/callback`
4. **Client Secret** - это секретная информация, не коммитьте его в Git!
5. Если вы используете `.env` файл, убедитесь, что он добавлен в `.gitignore`

## Troubleshooting

### Ошибка: "redirect_uri_mismatch"
- Убедитесь, что redirect URI в Google Cloud Console точно совпадает с URL вашего сайта
- Проверьте, что используется правильный протокол (http/https)
- Убедитесь, что нет лишних слешей в конце URL

### Ошибка: "invalid_client"
- Проверьте, что GOOGLE_CLIENT_ID и GOOGLE_CLIENT_SECRET правильно скопированы
- Убедитесь, что переменные окружения загружены (перезапустите приложение)

### Ошибка: "access_denied"
- Пользователь отменил авторизацию
- Проверьте настройки OAuth Consent Screen

## Дополнительная информация

- [Google OAuth 2.0 Documentation](https://developers.google.com/identity/protocols/oauth2)
- [Google Cloud Console](https://console.cloud.google.com/)

