# Многопользовательская архитектура (Multi-Tenancy) платформы

Данный документ описывает архитектуру мультитенантности платформы, реализованную для обслуживания нескольких изолированных "копий" сайта и ботов в рамках одной кодовой базы и одной базы данных.

## 1. Основная философия и подход

Архитектура системы построена на паттерне **Shared Database, Shared Schema (Row-level Isolation)**:
*   **Единая кодовая база** для всех проектов.
*   **Единая база данных** PostgreSQL.
*   **Изоляция на уровне записей (Row-Level Security)**: каждая запись, требующая изоляции, содержит внешний ключ `tenant_id` на модель `Tenant`.

### Почему этот подход?
*   Легче управлять инфраструктурой: один набор контейнеров, один пул коннектов к БД.
*   Менее сложная система миграций по сравнению со схемами (Schemas) базы данных.
*   Гибкость для суперпользователей, которым доступен просмотр всех данных системы в общей админке.

## 2. Модель тенанта (`Tenant`)
Модель `Tenant` (`tenants/models.py`) хранит все настройки конкретной платформы (например, quiz-code или quiz-islam):

*   **Идентификация**: `slug` (уникальный идентификатор, передается через ENV), `name` (название системы).
*   **Маршрутизация**: `domain` (перехватывается в middleware), `mini_app_domain` (для изоляции mini-app).
*   **Интеграция**: `bot_token`, `bot_username` (позволяет разным тенантам иметь собственных Telegram ботов).
*   **SEO и брендинг**: `site_name`, `site_description`, `theme_color`, `logo`, `meta_keywords`.

## 3. Middleware: Как определяется тенант запроса
`TenantMiddleware` (`tenants/middleware.py`) перехватывает каждый запрос и определяет, к какому тенанту он относится.

1.  Анализируется **только** `request.get_host()`. При `USE_X_FORWARDED_HOST=True` это `X-Forwarded-Host`,
    который nginx перезаписывает на `$host`, иначе `Host`. Префикс `www.` отбрасывается.
2.  Выполняется поиск в таблице `Tenant` (только `is_active=True`) по совпадению с полем `domain` или `mini_app_domain`.
    Результат кэшируется в памяти процесса (`clear_tenant_cache()` сбрасывает кэш).
3.  Найденный объект тенанта сохраняется в `request.tenant`.
4.  Если тенант не найден, `request.tenant = None`. Данные тенантов при этом не отдаются (пустые выборки / 404).

**Что намеренно игнорируется** (клиент мог бы подделать и выбрать чужого тенанта):
`X-Tenant-Slug`, `X-Tenant`, `X-Original-Host`, `X-Real-Host`, `Forwarded`, `Origin`, `Referer`.
Фоллбэка «единственный активный тенант» больше нет. В `nginx/nginx-prod.conf` эти заголовки обнуляются
во всех проксирующих location, а порты backend/mini_app в `docker-compose.local-prod.yml` слушают только
`127.0.0.1` — обойти nginx и подставить свой `X-Forwarded-Host` снаружи нельзя.

В DEBUG дополнительно поддерживается `NGROK_HOST` → `NGROK_TENANT_SLUG`.

## 4. Контроль доступа в Django Admin
Мы используем `TenantFilteredAdminMixin` (`tenants/mixins.py`), который переопределяет стандартное поведение `ModelAdmin`:

*   **Superuser (`is_superuser=True`)**: Видит абсолютно все данные. Поля 'tenant' доступны для редактирования.
*   **Staff-пользователи (контент-менеджеры)**: Обязаны быть привязаны к определенному `Tenant`.
    *   Тенант staff берётся **только** из `request.user.tenant` (домен запроса не учитывается).
        Staff без тенанта видит пустые списки.
    *   `get_queryset`: Возвращает только те данные, у которых `tenant == request.user.tenant`.
    *   Кастомные admin-view (генерация видео, бан из жалоб, отправка ответов) получают объекты через
        `self.get_queryset(request)`, а не `Model.objects.get(pk=...)` — иначе по id можно достать чужой объект.
    *   Инлайны миксин не наследуют: ограничивайте FK вручную (`formfield_for_foreignkey`), как в `TelegramAdminGroupInline`.
    *   Поля `is_superuser`, `groups`, `user_permissions` пользователя и раздел `DjangoAdmin` — только для суперпользователя.
    *   Создание записей: Поле `tenant` автоматически скрыто (`HiddenInput`) или вообще не отображается, и заполняется "под капотом" (`save_model`) значением `request.user.tenant`.
    *   Связи (Foreign Keys / M2M): Выпадающие списки связанных моделей (`formfield_for_foreignkey`) также фильтруются по тенанту текущего менеджера.

### Изоляция объектов без прямого ключа на `tenant`
Если модель не имеет прямого поля `tenant`, класс администратора задает атрибут `tenant_lookup` через двойное подчеркивание (django ORM lookups).
Например, для `SubtopicAdmin`:
```python
class SubtopicAdmin(TenantFilteredAdminMixin, admin.ModelAdmin):
    tenant_lookup = 'topic__tenant'
```
Для `UserChannelSubscription`:
```python
class UserChannelSubscriptionAdmin(TenantFilteredAdminMixin, admin.ModelAdmin):
    tenant_lookup = 'channel__tenant'
```

## 5. Изоляция в API (Django REST Framework)
Для API эндпоинтов создан миксин `TenantFilteredViewMixin` (`tenants/mixins.py`).
Его нужно добавлять основным классам `GenericAPIView` или `ModelViewSet`.

Особенности `TenantFilteredViewMixin`:
*   `get_queryset()`: Возвращает `qs.filter(tenant=request.tenant)`, исключая утечки данных в API. Возвращает пустой QuerySet, если тенант у текущего request не определен,
    а также для staff другого тенанта (или без тенанта). Суперпользователь получает всё — не используйте миксин
    для публичных ответов, которые кэшируются; для публичного API блога есть `TenantPublicQuerysetMixin` (`blog/views.py`).
*   `perform_create()`: Автоматически прикрепляет `request.tenant` к сохраняемой записи; staff другого тенанта получает 403.

Глобально в DRF `DEFAULT_PERMISSION_CLASSES = IsAuthenticatedOrReadOnly`. Публичные эндпоинты (платежи, вебхуки,
чтение Mini App) объявляют `AllowAny` явно.

## 5.1. Аутентификация Mini App (Telegram initData)

Пользователь Mini App определяется **только** по подписанному Telegram `initData`, а не по `telegram_id` из запроса.

*   Клиент: обёртка `fetch` в `mini_app/templates/base.html` добавляет заголовок `X-Telegram-Init-Data`
    (`Telegram.WebApp.initData`) ко всем same-origin запросам. Новых `fetch` это касается автоматически.
*   Django: `quiz_backend/accounts/telegram_webapp_auth.py`
    *   `validate_init_data()` — HMAC-SHA256 по алгоритму Telegram ключом `HMAC("WebAppData", bot_token)`,
        `bot_token` — `request.tenant.bot_token` (если пуст — `TELEGRAM_BOT_TOKEN`); проверка `auth_date`
        (`TELEGRAM_INIT_DATA_MAX_AGE`, по умолчанию 86400 с).
    *   `IsMiniAppUserOrReadOnly` — запись только с валидным initData; `telegram_id`/`author_telegram_id`/
        `reporter_telegram_id` в URL, теле или query должны совпадать с проверенным. `IsMiniAppUser` — то же для
        любых методов (аналитика), `IsMiniAppUserByPk` — pk в URL это telegram_id, `IsMiniAppFeedbackAuthor` — поле `user_id`.
    *   `POST /api/accounts/miniapp-users/auth/verify/` возвращает проверенного пользователя.
    *   Приватное чтение (by-telegram, statistics, me) — `IsMiniAppUser`/`IsMiniAppUserByPkStrict`;
        прогресс в публичных эндпоинтах тем/задач — через `verified_telegram_id_param` (без подписи — как аноним).
    *   Новый Mini App эндпоинт с записью должен использовать один из этих permission-классов.
*   mini_app (FastAPI): `mini_app/core/telegram_auth.py`
    *   Зависимость `verified_telegram_user` проверяет initData через Django `/auth/verify/` (кэш 5 минут)
        и отдаёт пользователя; `ensure_same_user()` — 403 при несовпадении `telegram_id` из пути.
    *   `get_proxy_headers()` пересылает `X-Telegram-Init-Data` в Django. `X-Tenant-Slug` больше не пересылается.
    *   Серверный рендер: httpOnly-cookie `tg_init_data` (ставится в `/api/verify-init-data`) для GET-запросов
        попадает в contextvar `request_init_data` и автоматически добавляется `DjangoAPIService._make_request`.
*   Приватные файлы (вложения сообщений, картинки обратной связи) раздаются через `config/protected_media.py`
    (X-Accel-Redirect на internal `/protected-media/`); прямые пути в `/media/` закрыты в nginx.
*   Важно: большинство `/api/*` на mini-домене nginx проксирует **прямо в Django** — защита живёт в Django,
    FastAPI-проверка — дополнительный слой для его собственных эндпоинтов.

## 6. Context Processors и SEO
`blog/context_processors.py` адаптирован для использования данных из `request.tenant`.
Теперь `seo_context()` и `dynamic_seo_context()` не используют захардкоженные `meta_description` и домены (например quiz-code.com). Вместо этого они:
1. Ищут `request.tenant` в текущем контексте (установленный `TenantMiddleware`).
2. Извлекают значения `domain`, `site_name`, `site_description`, `bot_username`, `meta_keywords`.
3. Устанавливают канонические URL, hreflang и JSON-LD структурированные данные.

Если тенант не определен (локальная разработка без правильного хоста или прямые запросы к IP), используются значения по умолчанию (fallback на `quiz-code`).

## 7. Модели данных, к которым применена изоляция (`tenant` FK)
К следующим моделям было добавлено поле `tenant` (внешний ключ на модель Tenant):

*   **Бизнес-модели**: `Topic`, `Subtopic`, `Task`.
*   **Изоляция платформ**: `TelegramGroup`.
*   **Пользователи**: `CustomUser` (через связанный объект / домен), `TelegramUser`, `MiniAppUser`, `TelegramAdmin`.
*   `UniqueConstraint`: Во избежание ошибок с уникальностью, ограничения `unique=True` были заменены на `UniqueConstraint(fields=['tenant', 'name'])`, чтобы разные клиенты могли использовать одинаковые имена категорий или username-ов пользователей.

## 8. Telegram-бот, Celery и интеграции

У фоновых процессов нет HTTP-хоста, поэтому тенант определяется иначе.

### Бот (`bot/`) — один процесс на всех тенантов
*   При старте (`bot/main.py`) читаются активные тенанты; для каждого `Tenant.bot_token` запускается свой
    `aiogram.Bot`, все — в одном диспетчере (`dp.start_polling(*bots)`). Кнопка Mini App каждого бота
    ведёт на `https://<mini_app_domain>` его тенанта.
*   Глобальный `TELEGRAM_BOT_TOKEN` (если он не совпадает ни с одним токеном тенанта) обслуживает тенант из
    `BOT_DEFAULT_TENANT_SLUG`, иначе — единственный активный тенант без своего токена. Если выбрать нельзя,
    бот работает без фильтра по тенанту (как раньше) и пишет предупреждение в лог.
*   `bot/tenancy.py`: `TenantContextMiddleware` по боту, получившему апдейт, кладёт id тенанта в contextvar
    `current_tenant_id`. Событие SQLAlchemy `do_orm_execute` ограничивает **все** ORM-запросы
    (SELECT/UPDATE/DELETE, ленивые загрузки) к моделям с `TenantScopedMixin` записями тенанта и общими
    (`tenant_id IS NULL`); `before_flush` проставляет `tenant_id` новым записям.
    Осознанный обход: `.execution_options(skip_tenant_filter=True)`.
*   Сырой SQL (`text()`) фильтром не покрывается — в нём `tenant_id` указывается явно.
*   Новый тенант подхватывается после перезапуска контейнера бота.

### Старые записи без тенанта
Записи, созданные до мультитенантности (или ботом до перехода на ботов тенантов), имеют `tenant_id = NULL`
и считаются общими. Привязать их к тенанту:
```bash
python manage.py assign_tenant_to_legacy_rows --slug it-dev            # отчёт
python manage.py assign_tenant_to_legacy_rows --slug it-dev --apply    # записать
```

### Django и Celery
*   Telegram-действия (публикация задач, удаление сообщений, рассылка, назначение админов каналов, уведомления,
    возврат Stars) выполняются ботом тенанта: `tenants/scoping.bot_token_for(tenant)` — токен тенанта или
    глобальный, если у тенанта он не задан.
*   `Webhook`, `GlobalWebhookLink`, `DefaultLink`, `MainFallbackLink`, `SocialMediaCredentials` выбираются через
    `tenants/scoping.for_tenant_or_shared`: записи тенанта задачи + общие (`tenant=NULL`), чужие — никогда.
*   `TENANT_SLUG` в `docker-compose.yml` кодом не используется.

### 🚀 Подробное руководство: Разворачивание нового инстанса

Инфраструктура спроектирована так, чтобы добавление нового тенанта (например, `quiz-islam.com`) занимало минимум времени и не требовало отдельной базы данных. Безопасно развернуть новый инстанс можно по следующим шагам:

#### Шаг 1: Создание записи в мастер-системе (Django Admin)
1. Зайдите в админ-панель основного домена (например, `https://quiz-code.com/admin`) под учетной записью **Superuser**.
2. Перейдите в раздел **Tenants -> Тенанты** и нажмите "Добавить тенант".
3. Заполните данные нового инстанса:
   - **`slug`**: `quiz-islam` (идентификатор тенанта для команд и `BOT_DEFAULT_TENANT_SLUG`).
   - **`Name`**: `Quiz Islam`
   - **`domain`**: `quiz-islam.com` (Без `https://` и `www`)
   - **`mini_app_domain`**: `mini.quiz-islam.com`
   - **`bot_token`** и **`bot_username`**: токен и имя нового бота из @BotFather.
   - **SEO параметры**: `site_name` (например, *QuizHub: Islam*), `site_description`, `meta_keywords`, `theme_color`, загрузите `logo`.
4. Нажмите **Сохранить**.

#### Шаг 2: Настройка DNS
В панели вашего регистратора доменов (или Cloudflare) добавьте A-записи для нового домена:
- A-запись для `quiz-islam.com` указывающая на IP-адрес вашего сервера (где запущен Nginx/Django).
- A-запись для `mini.quiz-islam.com` указывающая на тот же IP-адрес (для Mini-App).

#### Шаг 3: Настройка Nginx и SSL-сертификатов
Поскольку трафик идет через Nginx, необходимо сконфигурировать `server` блоки так, чтобы Nginx перехватывал запросы для новых доменов и передавал их основному контейнеру `quiz_backend:8000` и `mini_app:8080`.
*(Совет: Если вы используете Nginx Proxy Manager (NPM), просто добавьте новые Proxy Hosts для этих доменов и выпустите Let's Encrypt сертификаты).*

#### Шаг 4: Перезапуск бота
Основной монолит `quiz_backend` и mini_app **не нужно перезагружать** — они определяют тенанта по домену
(`TenantMiddleware`). Боту нужно подхватить новый `bot_token`: перезапустите контейнер бота —
он запустит ботов всех активных тенантов в одном процессе.

```bash
docker compose -f docker-compose.local-prod.yml restart telegram_bot
```

#### Шаг 5: Добавление контент-менеджеров
1. Снова зайдите в `quiz-code.com/admin` (от имени Superuser).
2. Откройте **Accounts / Пользователи** -> Создайте нового пользователя (Staff).
3. Обязательно присвойте ему новосозданный тенант в поле `tenant` (выберите `quiz-islam`).
4. Выдайте права доступа (Permissions) к редактированию `Tasks`, `Topics`, `Subtopics`.
5. Выдайте права "Персонал" (`is_staff = True`).
6. Сохраните.

Теперь этот менеджер может авторизоваться по адресу `https://quiz-islam.com/admin` и он **гарантированно будет видеть только свои вопросы, свои категории, свою платформу и пользователей своего бота!** Данные `quiz-code` для него полностью скрыты за счет `TenantFilteredAdminMixin`.

Таким образом, монолит Django остается единым центром управления и хранения всех данных (что упрощает бекапы и обновления кода), а платформы работают как независимые SaaS-сайты.

---
*Документация сгенерирована автоматически системой после завершения Phase 3 рефакторинга мультитенантности.*
