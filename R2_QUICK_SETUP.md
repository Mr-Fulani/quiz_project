# Быстрая настройка R2 Custom Domain

## ⚠️ Важно: Custom Domain обязателен!

Без Custom Domain **не будут работать**:
- ❌ Telegram Bot (не сможет отправить фото)
- ❌ Telegram Mini App (не отобразит изображения)
- ❌ Django API (вернет недоступные URL)

## Шаги настройки (5 минут)

### 1. Настройте Custom Domain в Cloudflare

1. Откройте [Cloudflare Dashboard](https://dash.cloudflare.com)
2. Перейдите в **R2** → выберите бакет `quiz-hub-prod`
3. Перейдите в **Settings** → **Public Access**
4. Нажмите **Connect Domain**
5. Выберите ваш домен (например, `quiz-code.com`)
6. Создайте поддомен: `cdn.quiz-code.com` или `media.quiz-code.com`
7. Cloudflare автоматически настроит DNS (может занять 1-2 минуты)

### 2. Добавьте в .env на сервере

```bash
# В файле .env на сервере добавьте:
R2_PUBLIC_DOMAIN=cdn.quiz-code.com
```

(Замените `cdn.quiz-code.com` на ваш поддомен)

### 3. Перезапустите контейнеры

```bash
docker compose restart quiz_backend telegram_bot
```

### 4. Проверьте логи

```bash
docker compose logs quiz_backend | grep "R2 публичный домен"
```

Должно быть:
```
R2 публичный домен настроен: cdn.quiz-code.com
```

### 5. Проверьте доступность

```bash
# Проверка через curl
curl -I https://cdn.quiz-code.com/prod/images/test.png

# Должен вернуть HTTP 200 или 404 (если файла нет), но НЕ SSL ошибку
```

## Как это работает

После настройки все компоненты будут использовать Custom Domain:

1. **Telegram Bot** → отправляет фото через `https://cdn.quiz-code.com/prod/images/...`
2. **Mini App** → отображает изображения через `<img src="https://cdn.quiz-code.com/prod/images/...">`
3. **Django API** → возвращает URL `https://cdn.quiz-code.com/prod/images/...`

## Структура файлов в R2

```
quiz-hub-prod/
├── prod/          # Продакшен файлы (когда DEBUG=False)
│   ├── images/
│   └── videos/
└── dev/           # Файлы разработки (когда DEBUG=True)
    ├── images/
    └── videos/
```

## Проблемы?

- **SSL ошибка** → Проверьте настройки Custom Domain в Cloudflare Dashboard
- **404 ошибка** → Проверьте путь к файлу (должен быть `prod/images/...` или `dev/images/...`)
- **Файлы не загружаются** → Проверьте `R2_PUBLIC_DOMAIN` в `.env` и перезапустите контейнеры

## Подробная документация

См. `R2_CUSTOM_DOMAIN_SETUP.md` для детальной информации.

