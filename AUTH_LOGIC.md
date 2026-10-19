# Логика авторизации

> Актуально на 2026-10-18. Описывает фактический код; при изменении логики обновляйте этот файл.

Система поддерживает:
- **Telegram Login Widget** — вход на сайт через Telegram (`social_auth/services.py`, `TelegramAuthService`)
- **GitHub OAuth 2.0** (`GitHubAuthService`) и **Google OAuth** (`GoogleAuthService`)
- **Telegram Mini App** — пользователь определяется по подписанному `initData` (см. раздел ниже)

Все поиски пользователей и соцаккаунтов выполняются **в рамках тенанта** запроса (`request.tenant`).

---

## Главное правило безопасности

Аккаунт сайта связывается с внешним входом **только по идентификатору, который нельзя выбрать самому**:
`telegram_id` (подписан Telegram), `provider_user_id` соцаккаунта, email (для GitHub/Google).

**Никогда не связываем по username.** Username в Telegram и логин GitHub выбирает сам пользователь:
назвавшись `admin`, можно было войти в чужой аккаунт. Эта логика удалена из Telegram-логина,
GitHub-логина, `ProfileByTelegramID`, `link_users` и `MiniAppUserCreateSerializer` — не возвращайте её.

Связать вход с существующим аккаунтом осознанно можно, будучи уже авторизованным на сайте (сценарий ниже).

---

## 🟢 Telegram Login Widget

`TelegramAuthService.process_telegram_auth(data, request)`:

1. Проверка подписи данных виджета и `auth_date`.
2. Поиск `SocialAccount(provider='telegram', provider_user_id=telegram_id, tenant=tenant)`.
   - Найден → вход в его пользователя, обновление данных соцаккаунта, автосвязывание
     (`TelegramUser`, `MiniAppUser`, `TelegramAdmin` по `telegram_id`), объединение статистики Mini App.
3. Не найден:
   - Пользователь уже авторизован на сайте → Telegram привязывается к **текущему** пользователю.
   - Иначе `_get_or_create_user(data, tenant)`:
     1. `CustomUser` с этим `telegram_id` в тенанте (без тенанта — среди `tenant=None`) → он.
     2. Иначе создаётся **новый** пользователь. `User.username` генерируется
        (`first_name_last_name`, `first_name`, `tg_<telegram_username>` или `user_<telegram_id>`) с суффиксом для уникальности;
        Telegram username хранится в `SocialAccount.username`.

## 🔵 GitHub OAuth

`GitHubAuthService.process_github_auth(...)`:

1. Поиск `SocialAccount(provider='github', provider_user_id=github_id, tenant=tenant)` → вход.
2. Не найден: авторизованный пользователь → привязка к нему; иначе `_get_or_create_user(user_info, tenant)`:
   1. Пользователь с тем же **email** в тенанте → он (обновляются только пустые поля).
   2. Иначе создаётся новый пользователь (username на основе логина GitHub, с суффиксом при занятости).

Google OAuth устроен так же (поиск по `provider_user_id`, затем по email, затем создание).

---

## 📱 Telegram Mini App

Подробно — в `MULTI_TENANT_ARCHITECTURE.md`, раздел «Аутентификация Mini App». Кратко:

- Клиент отправляет подписанный Telegram `initData` в заголовке `X-Telegram-Init-Data`
  со всеми same-origin запросами (обёртка `fetch` в `mini_app/templates/base.html`).
- Django проверяет HMAC-SHA256 подпись **токеном бота тенанта** (`Tenant.bot_token`, при его отсутствии —
  `TELEGRAM_BOT_TOKEN`) и срок `auth_date` (`TELEGRAM_INIT_DATA_MAX_AGE`, по умолчанию 24 ч):
  `quiz_backend/accounts/telegram_webapp_auth.py`.
- Любой `telegram_id` в URL, теле или query (`telegram_id`, `author_telegram_id`, `reporter_telegram_id`,
  `user_id` в обратной связи) обязан совпадать с проверенным — иначе 401/403.
- `mini_app` (FastAPI) не проверяет подпись сам, а спрашивает Django
  (`POST /api/accounts/miniapp-users/auth/verify/`), кэширует результат на 5 минут
  (`mini_app/core/telegram_auth.py`) и подставляет проверенный `telegram_id` в запросы к Django.
- Приватные данные (полный профиль, статистика, `me`) отдаются только самому пользователю с валидным initData;
  список всех пользователей — только админам. Публичный профиль и топ открыты и скрывают поля приватных профилей.
- Персональный прогресс в темах/задачах учитывается, только если `telegram_id` совпадает с подписанным
  (`verified_telegram_id_param`); иначе ответ строится как для анонима.
- Серверный рендер страниц mini_app: после `/api/verify-init-data` initData хранится в httpOnly-cookie
  `tg_init_data` (24 ч) и пересылается в Django для GET-запросов. Для записи cookie не используется — только заголовок.
- Без Telegram (в обычном браузере) запись и приватные данные в Mini App недоступны.

---

## 🔗 Автосвязывание сущностей

`SocialAccount.auto_link_existing_users()` после входа связывает `TelegramUser`, `MiniAppUser`,
`TelegramAdmin` по `telegram_id` в том же тенанте. `MiniAppUser` связывается с `DjangoAdmin` только через
`linked_custom_user`, у которого `is_staff`/`is_superuser`.

## 📊 Синхронизация данных

Существующие данные не перезаписываются: обновляются только пустые поля (`first_name`, `last_name`,
`email`, `avatar`, ссылки), данные `SocialAccount` обновляются всегда. Статистика и настройки сохраняются.

## ⚠️ Прочие меры безопасности

- Определение тенанта — только по `Host`/`X-Forwarded-Host` (nginx перезаписывает его на `$host`);
  заголовки `X-Tenant-Slug`, `X-Original-Host`, `Forwarded`, `Origin`, `Referer` игнорируются.
- DRF по умолчанию `IsAuthenticatedOrReadOnly`; публичные эндпоинты объявляют `AllowAny` явно.
- В админке поля `is_superuser`, `groups`, `user_permissions` меняет только суперпользователь;
  раздел DjangoAdmin доступен только суперпользователю.
- CSRF в GitHub OAuth проверяется через `state`.
