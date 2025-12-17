# Как получить учетные данные Cloudflare R2

## Шаг 1: Войдите в Cloudflare Dashboard

1. Откройте https://dash.cloudflare.com/
2. Войдите в свой аккаунт

## Шаг 2: Найдите Account ID

**Способ 1: Из URL**
- После входа в Dashboard посмотрите на URL в браузере
- URL будет примерно таким: `https://dash.cloudflare.com/ВАШ_ACCOUNT_ID/...`
- Скопируйте `ВАШ_ACCOUNT_ID` из URL

**Способ 2: Из правого сайдбара**
- В правом нижнем углу Dashboard найдите секцию "Account ID"
- Скопируйте значение

**Способ 3: Через настройки аккаунта**
- Кликните на иконку профиля в правом верхнем углу
- Выберите "My Profile"
- Account ID будет отображен в информации об аккаунте

## Шаг 3: Создайте R2 API Token

1. В левом меню Dashboard найдите **"R2"** (Object Storage)
2. Кликните на **"Manage R2 API Tokens"** (или перейдите по прямой ссылке: https://dash.cloudflare.com/?to=/:account/r2/api-tokens)
3. Нажмите **"Create API token"**
4. Заполните форму:
   - **Token name**: например, "quiz-project-r2-token"
   - **Permissions**: выберите **"Object Read & Write"** и **"Object List"**
   - **TTL**: можно оставить пустым (без срока действия) или установить срок
   - **R2 buckets**: выберите ваш бакет `quiz-hub-prod` или "All buckets"
5. Нажмите **"Create API Token"**

## Шаг 4: Скопируйте учетные данные

После создания токена вы увидите:

1. **Access Key ID** - длинная строка (например: `a1b2c3d4e5f6g7h8i9j0...`)
2. **Secret Access Key** - очень длинная строка (например: `x1y2z3a4b5c6d7e8f9g0h1i2j3k4l5m6n7o8p9q0...`)

⚠️ **ВАЖНО**: Secret Access Key показывается только один раз! Скопируйте его сразу и сохраните в безопасном месте.

## Шаг 5: Добавьте в .env файл

Откройте файл `.env` и добавьте:

```bash
# Cloudflare R2 настройки
USE_R2_STORAGE=True
R2_ACCOUNT_ID=ваш_account_id_из_шага_2
R2_ACCESS_KEY_ID=ваш_access_key_id_из_шага_4
R2_SECRET_ACCESS_KEY=ваш_secret_access_key_из_шага_4
R2_BUCKET_NAME=quiz-hub-prod
```

## Пример заполненного .env

```bash
USE_R2_STORAGE=True
R2_ACCOUNT_ID=1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o6p
R2_ACCESS_KEY_ID=a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0
R2_SECRET_ACCESS_KEY=x1y2z3a4b5c6d7e8f9g0h1i2j3k4l5m6n7o8p9q0r1s2t3u4v5w6x7y8z9a0b1c2d3e4f5g6h7i8j9k0l1m2n3o4p5q6r7s8t9u0
R2_BUCKET_NAME=quiz-hub-prod
```

## Проверка

После добавления переменных перезапустите контейнеры:

```bash
docker compose restart quiz_backend telegram_bot
```

Проверьте логи:
```bash
docker compose logs quiz_backend | grep "R2 хранилище"
```

Должно появиться:
```
R2 хранилище настроено: бакет=quiz-hub-prod, окружение=prod
```

## Если потеряли Secret Access Key

Если вы потеряли Secret Access Key:
1. Перейдите в "Manage R2 API Tokens"
2. Найдите ваш токен
3. Удалите его
4. Создайте новый токен (см. Шаг 3)
5. Скопируйте новые учетные данные

## Безопасность

⚠️ **Никогда не коммитьте .env файл в git!**
- Убедитесь, что `.env` в `.gitignore`
- Не делитесь учетными данными
- Используйте разные токены для разных окружений (dev/prod)

