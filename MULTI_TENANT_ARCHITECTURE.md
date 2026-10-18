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
    *   Новый Mini App эндпоинт с записью должен использовать один из этих permission-классов.
*   mini_app (FastAPI): `mini_app/core/telegram_auth.py`
    *   Зависимость `verified_telegram_user` проверяет initData через Django `/auth/verify/` (кэш 5 минут)
        и отдаёт пользователя; `ensure_same_user()` — 403 при несовпадении `telegram_id` из пути.
    *   `get_proxy_headers()` пересылает `X-Telegram-Init-Data` в Django. `X-Tenant-Slug` больше не пересылается.
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

## 8. Изоляция рабочих процессов (Celery) и Mini App в Docker

> ⚠️ **Состояние на 2026-10-18: описанное ниже — целевая схема, а не текущий код.**
> Переменная `TENANT_SLUG` задаётся в `docker-compose.yml`, но ни бот (`bot/`), ни mini_app, ни Celery её не читают.
> Бот работает с одним глобальным `TELEGRAM_BOT_TOKEN` и не фильтрует данные по тенанту; Celery-задачи и сервисы
> публикации используют глобальный токен и глобальные `Webhook`/`SocialMediaCredentials`/`DefaultLink`.
> Подробности и план — в `TECH_DEBT.md` (раздел «Изоляция: бот и Celery»).

Так как фоновые Worker'ы (Celery) и асинхронные скрипты Telegram-ботов не зависят от HTTP запросов, они не имеют `request.get_host()`.
Поэтому для них переменная окружения `TENANT_SLUG` пробрасывается прямо в файле `docker-compose.yml`.

Пример из `docker-compose.yml`:
```yaml
  mini_app:
    environment:
      - TENANT_SLUG=${TENANT_SLUG:-quiz-code}
```

Скрипты (например, Telegram бот или backend FastAPI Mini-App) используют `os.getenv('TENANT_SLUG')` для того, чтобы:
1. Запросить у Django API данные конкретного `Tenant`.
2. Запускать бот с правильным токеном тенанта.
3. Отправлять/получать webhook именно для этого домена.

### 🚀 Подробное руководство: Разворачивание нового инстанса

Инфраструктура спроектирована так, чтобы добавление нового тенанта (например, `quiz-islam.com`) занимало минимум времени и не требовало отдельной базы данных. Безопасно развернуть новый инстанс можно по следующим шагам:

#### Шаг 1: Создание записи в мастер-системе (Django Admin)
1. Зайдите в админ-панель основного домена (например, `https://quiz-code.com/admin`) под учетной записью **Superuser**.
2. Перейдите в раздел **Tenants -> Тенанты** и нажмите "Добавить тенант".
3. Заполните данные нового инстанса:
   - **`slug`**: `quiz-islam` (Обязательно! Это ключ привязки для Docker).
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

#### Шаг 4: Запуск контейнеров бота и mini-app для нового тенанта
Основной монолит `quiz_backend` **не нужно перезагружать** — он автоматически обслужит `quiz-islam.com`, вытягивая правильные данные с помощью `TenantMiddleware`. 

Однако, скриптам Telegram бота и локальным фоновым процессам необходимо сообщить, для какого проекта они работают (так как у них нет HTTP hostname запроса). Для этого мы передаем `TENANT_SLUG`.

На сервере можно запустить отдельные инстансы бота для нового тенанта:

```bash
# Вариант запуска через Docker Compose с передачей переменной окружения
export TENANT_SLUG=quiz-islam
docker-compose up -d telegram_bot mini_app
```
*(При запуске контейнер `telegram_bot` считает переменную `TENANT_SLUG=quiz-islam`, подключится к общей базе PostgreSQL, вытащит свой уникальный `bot_token` и начнет обрабатывать сообщения для своего изолированного бота).*

**Альтернатива**: В Production-среде вы можете продублировать блок `telegram_bot` в `docker-compose.yml` (назвав его `telegram_bot_islam`) и прямо там прописать `TENANT_SLUG=quiz-islam`, чтобы управлять всеми ботами в одном файле оркестрации.

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
