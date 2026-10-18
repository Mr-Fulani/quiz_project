# Технический долг

> Ведётся по итогам аудита 2026-10-18 (производительность, мёртвый код, изоляция данных, админка, SEO).
> Закрыли пункт — удалите его отсюда (или перенесите в «Сделано») в том же коммите.
> Приоритеты: 🔴 критично · 🟠 высокий · 🟡 средний · 🟢 низкий.

---

## 👤 Нужно от владельца проекта (без этого не задеплоить / не закрыть)

- [ ] 🔴 **Добавить `REDIS_PASSWORD` в `.env` на сервере** до следующего деплоя — без него
      `docker-compose.local-prod.yml` не стартует (так задумано). Без символов `@ : / ?`.
- [ ] 🔴 **`backup.sql` в git и на GitHub**: 22 хеша паролей, 15 email, 85 сессий, 60 личных сообщений.
      Нужно: удалить из истории (`git filter-repo --path backup.sql --invert-paths` + force push — меняет
      историю, решение за вами), сменить пароли затронутых аккаунтов, сбросить сессии. Если репозиторий
      публичный — считать данные утёкшими.
- [ ] 🟠 Проверить, что у каждого тенанта в админке заполнен `bot_token` — им проверяется подпись Mini App.
- [ ] 🟠 Задать `TELEGRAM_WEBHOOK_SECRET`, если используется webhook `/api/webhooks/telegram/`
      (сейчас при пустом значении запросы отклоняются).
- [ ] 🟡 Порты 8001/8080/5433/8002 теперь только на `127.0.0.1`. Если вы ходили в админку/API по `IP:8001`
      снаружи — это больше не работает (используйте домен или SSH-туннель).
- [ ] 🟡 Решить, нужен ли `SOCIAL_MEDIA_CALLBACK_SECRET` для Make.com (и прописать заголовок в сценарии).
- [ ] 🟡 Подтвердить: Mini App в обычном браузере (без Telegram) теперь только читает — запись требует initData.
- [ ] 🟢 Прогнать `tasks/tests` и `topics/tests` в Docker (локально без Docker они не запускались:
      требуют S3/Telegram/генерации изображений).

---

## 🔐 Безопасность и изоляция данных

### Mini App
- [ ] 🟠 Чтение без initData всё ещё открыто: `GET /api/accounts/miniapp-users/by-telegram/<id>/`,
      `/profile/by-telegram/<id>/`, `/miniapp-users/statistics/?telegram_id=`, `GET /miniapp-users/` (список с
      `birth_date`, `gender`). Причина: серверный рендер страниц mini_app (`routers/pages.py`) берёт
      `telegram_id` из cookie/заголовка. План: выдавать подписанную сессию после `verify-init-data`
      (httpOnly cookie) и требовать её на чтении приватных данных; публичный профиль — через
      `PublicMiniAppUserSerializer` с учётом `is_profile_public`.
- [ ] 🟡 `mini_app/routers/pages.py` доверяет `telegram_id` из cookie/`X-Telegram-User-Id` (только чтение).
- [ ] 🟡 `LanguageMiddleware` меняет язык на глобальном синглтоне `localization_service` — гонка между
      запросами (пользователь может получить чужой язык).
- [ ] 🟢 Логи mini_app пишут полные профили и заголовки запросов (PII).

### Бот и Celery (тенанты не учитываются)
- [ ] 🔴 В боте нет проверки админа у части хендлеров: `bot/handlers/admin_menu.py` (`upload_json`,
      `publish_by_id`, удаление задачи по ID, `create_quiz`, …) и `bot/handlers/feedback.py` (просмотр,
      ответ, удаление обратной связи). Любой может прислать callback_data и удалить задачу.
- [ ] 🟠 Бот не знает о тенантах: один глобальный `TELEGRAM_BOT_TOKEN`, запросы к БД без `tenant_id`,
      `is_admin` по `telegram_id` без тенанта (админ одного тенанта — админ бота для всех).
- [ ] 🟠 Celery и сервисы публикации используют глобальный `TELEGRAM_BOT_TOKEN`
      (`tasks/services/telegram_service.py`, `platforms/services.py`, `feedback/services.py`, …).
- [ ] 🟠 Исходящие вебхуки глобальные: `webhooks/services.py`, `config/tasks.py`
      (`Webhook.objects.filter(is_active=True)`) — задачи всех тенантов уходят во все вебхуки.
      Так же `SocialMediaCredentials`, `DefaultLink`, `MainFallbackLink`, `GlobalWebhookLink`.
- [ ] 🟠 `platforms/admin.py` `send_post_view`: каналы — `TelegramGroup.objects.all()`, рассылка
      подписчикам всех тенантов.
- [ ] 🟡 ~44 места ищут `MiniAppUser` по `telegram_id` без тенанта (`tasks/comment_views.py`,
      `tasks/notification_service.py`, …): `.get()` даст MultipleObjectsReturned, `.first()` — чужой профиль.
- [ ] 🟡 Аналитика Mini App (`accounts/api/mini_app_analytics.py`) считает донаты/подписки/активность
      по всем тенантам (доступ уже ограничен админом тенанта).
- [ ] 🟡 Письма с формы контактов уходят на глобальный `EMAIL_ADMIN`, а не `tenant.contact_email`.

### Django
- [ ] 🟠 Приватные медиа публичны: `message_attachments/%Y/%m/%d/<имя>` раздаётся nginx `/media/` без
      проверки; то же `feedback_images/`, `task_comments/`. План: UUID-имена, `internal` location +
      `X-Accel-Redirect` из `download_attachment`, либо приватный R2-бакет с presigned URL.
      Плюс `Content-Disposition` в `download_attachment` не экранирует имя файла.
- [ ] 🟠 Вход не привязан к тенанту: `CustomUser.username` уникален глобально, логин тенанта A работает на B.
      Нужен tenant-aware backend + `UniqueConstraint(tenant, username)` (миграция данных).
- [ ] 🟡 Sitemaps (`blog/sitemaps.py`) и robots берут домен из `Site #1` и содержат объекты всех тенантов.
- [ ] 🟡 `tenant` везде `null=True`, часто `SET_NULL`: удаление тенанта превращает его данные в «глобальные».
      Глобальные unique: `Category.slug`, `Post.slug`, `Project.slug`, `Webhook.url`, `SocialAuthSettings.provider`.
- [ ] 🟡 `DisableCSRFForAPI` снимает CSRF со всех `/api/`, `/auth/telegram*`, `*/telegram/*` и мутирует view
      глобально. Перейти на точечный `@csrf_exempt` для вебхуков.
- [ ] 🟡 Админ-действия по GET (бан/разбан из жалоб, «Отправить» ответ, генерация видео) — CSRF через `<img>`.
      Перевести на POST.
- [ ] 🟡 Удаление задачи в админке удаляет Telegram-сообщения `message_id-2 … message_id+1`
      (`tasks/admin.py` `delete_queryset`) — заденет соседние посты. Нужно хранить все id сообщений поста
      (JSON-поле + миграция) и удалять только их.
- [ ] 🟡 CORS/CSRF trusted origins доверяют всем тенантам с credentials (`settings.py`).
- [ ] 🟡 `profile_view` и `custom_password_reset_view` (`accounts/views.py`) ищут пользователя без тенанта.
- [ ] 🟢 `TaskSkipView` без тенанта ищет задачу по всем тенантам.
- [ ] 🟢 `SubtopicListView` и `SubtopicCreateView` сломаны (ждут `topic_id`, которого нет в URL).
- [ ] 🟢 `_tenant_cache` в памяти процесса: `clear_tenant_cache()` чистит только один воркер.
- [ ] 🟢 `Tenant.bot_token` и секреты соцсетей хранятся и показываются в админке открытым текстом.
- [ ] 🟢 Сторонние админки без изоляции: `authtoken` (TokenProxy), `django_celery_beat`, `Group`, `Site` —
      ограничить суперпользователем.

---

## ⚡ Производительность

- [ ] 🔴 N+1 в `topics/views.py` `subtopic_detail_simple` (2 запроса на задачу) + mini_app вызывает его
      дважды за загрузку (`mini_app/routers/pages.py` `get_subtopic_detail` и `get_tasks_for_subtopic`).
- [ ] 🔴 `SubtopicWithTasksSerializer` — ~13 запросов на подтему; аннотация `tasks_count` не используется.
- [ ] 🔴 Топ пользователей Mini App — сотни запросов: `get_rating` пересчитывает аннотированный `rating`,
      `quizzes_completed`/`average_score` — property с COUNT, логи заголовков на каждого пользователя.
- [ ] 🟠 `blog/context_processors.py` `personal_info` — тяжёлая агрегация на каждой странице без кэша.
- [ ] 🟠 `dynamic_seo_context` вызывает `connection.close()` (ломает `CONN_MAX_AGE`), лишние запросы;
      в тестах логирует `name 'connection' is not defined` — проверить импорт.
- [ ] 🟠 `config/settings_production.py` нигде не подключается — Redis-кэш и прочее оттуда в проде не действуют.
      Решить: удалить или подключить.
- [ ] 🟠 JS mini_app не кэшируется: `location ~* \.js$` в nginx перебивает `/static/` (no-store), cache-buster
      добавляет `force=time()`.
- [ ] 🟠 `mini_app/templates/base.html`: ~1400 строк inline JS, Stripe/QR/ionicons синхронно на всех страницах.
- [ ] 🟠 `blog/static/blog/js/font-awesome.min.js` (1.5 МБ) на каждой странице вместе с CSS-версией;
      highlight.js и GSAP глобально.
- [ ] 🟡 Новый `httpx.AsyncClient` на каждый запрос в mini_app и логирование всего ответа Django.
- [ ] 🟡 Логи INFO с `=== DEBUG` на каждый запрос; `echo=True` у SQLAlchemy в боте.
- [ ] 🟡 Индексы: `Task.translation_group_id`, `TaskTranslation(task, language)`, `Task(subtopic, difficulty)`.
- [ ] 🟡 `TenantMiddleware`: промахи не кэшируются; кэш перенести в Redis с TTL.
- [ ] 🟢 `WHITENOISE_AUTOREFRESH=True` в проде; `CONN_HEALTH_CHECKS` не включён.

## 🔎 SEO

- [ ] 🔴 Canonical и hreflang на большинстве страниц указывают на главную (`context_processors.py` `seo_context`).
- [ ] 🔴 www-редирект в nginx ведёт все домены на `quiz-code.com` (`nginx-prod.conf`, server с `www.*`).
- [ ] 🔴 Текст вопроса квиза только на картинке (`quiz_subtopic.html`) — для поисковика thin content.
- [ ] 🟠 Fuzzy-поиск тем/подтем (`iregex`) плодит дубли URL; пустые страницы отдают 200 (soft 404);
      `difficulty` принимает любое значение.
- [ ] 🟠 Slug без транслитерации (`slugify` по кириллице даёт пустой slug).
- [ ] 🟠 Захардкоженные/одинаковые title («QuizHub», «Quiz Python, Go…» на всех тенантах).
- [ ] 🟠 hreflang для постов без переводов; `Disallow` в robots не работает из-за языковых префиксов;
      noindex отсутствует на профилях, статистике, `/swagger/`, сбросе пароля.
- [ ] 🟡 JSON-LD: breadcrumbs выводятся как Python-dict, SearchAction на несуществующий поиск, `logo.png` 404,
      дублирующиеся Article/BlogPosting.
- [ ] 🟡 Mini App: `X-Robots-Tag: noindex` в nginx, share-страницы с `index,follow`.
- [ ] 🟢 Корень `/` отдаёт 200 с meta-refresh вместо 301/302.

## 🗂 Админка

- [ ] 🟠 Нельзя создать задачу сразу на N языках; `translation_group_id` readonly; инлайн перевода без `max_num=1`.
- [ ] 🟠 В списке задач нет текста вопроса и поиска по нему (`translations__question`).
- [ ] 🟠 Публикация в Telegram/соцсети и генерация картинок синхронно в запросе (`time.sleep`) → 504.
      Перевести в Celery по образцу генерации видео.
- [ ] 🟠 `feedback/admin.py` `save_formset`: картинка ответа сохраняется дважды.
- [ ] 🟠 `blog/admin.py` `send_to_telegram_action`: файлы закрываются после первого канала.
- [ ] 🟡 Ссылка «Комментарий #N» ведёт на незарегистрированный `TaskComment` (404).
- [ ] 🟡 `topics/admin.py`: превью через удалённый `allow_tags` (сырой HTML), счётчики N+1.
- [ ] 🟡 `autocomplete_fields` нигде; у задачи тема/подтема — raw_id.
- [ ] 🟡 Возврат Stars, смена статуса доната без подтверждения; `amount`/`status` редактируемы.
- [ ] 🟡 JSON-импорт: нет dry-run, проверки дублей, атомарности; сотни плашек сообщений.
- [ ] 🟢 `LANGUAGE_CODE='en'`, не задан `site_header`; 52 модели в индексе без группировки.
- [ ] 🟢 Бот-админка: удаление без подтверждения, нет `/cancel` в FSM.

## 🧹 Мёртвый код и мусор в репозитории

- [ ] 🟠 В git: `node_modules/` (6667 файлов, удаление не закоммичено), `quiz_backend/staticfiles/` (1916),
      пользовательские `media/` (~300), `.coverage`, egg-info, `postEvent`, `temp_ru.po`, `project_tree.txt`.
      Сделать `git rm --cached` отдельным коммитом и дополнить `.gitignore`.
- [ ] 🟠 `.gitignore`: правило `*/migrations/*.py` молча игнорирует новые миграции — убрать.
- [ ] 🟡 ~90 устаревших `.md`-отчётов в корне (`FIX_*`, `URGENT_*`, `FINAL_*`, `SUCCESS_*`) и разовые скрипты;
      ценное (архитектура, интеграции) — в `docs/`.
- [ ] 🟡 Неиспользуемые модули: `tasks/notification_service.py`, `tasks/utils/cache_utils.py`, `tasks/filters.py`,
      `platforms/widgets.py`, `mini_app/services/django_api.py`, `bot/api/notify.py`; JS `carousel.js`,
      `gallery*.js`, `matrix.js`, `poll-explanation.js`; шаблоны `home.html`, `top_users_old.html`, `top_users_clean.html`.
- [ ] 🟡 Celery-заглушки без вызова: `send_contact_form_email`, `generate_og_image`, `cleanup_old_media_files`,
      `process_uploaded_file`.
- [ ] 🟡 Дубли bot ↔ quiz_backend: генерация картинок кода, вебхуки, `default_link_service`, импорт задач.
- [ ] 🟢 Остатки alembic (`alembic.ini`, `migrations/`), `requirements*.backup*`, неиспользуемые зависимости
      (APScheduler, SQLAlchemy в backend, black/autopep8 в рантайме).
- [ ] 🟢 Тестовый хендлер `/test` подключён в боте (`bot/handlers/test.py`).

---

## ✅ Сделано (2026-10-18)

- Тенант определяется только по Host/X-Forwarded-Host; nginx обнуляет подделываемые заголовки; порты — 127.0.0.1.
- Mini App: подпись initData проверяется в Django токеном бота тенанта; запись только от проверенного пользователя;
  убран fallback-парсинг initData; FastAPI без debug и CORS `*`.
- DRF по умолчанию `IsAuthenticatedOrReadOnly`; API блога только чтение и только свой тенант.
- Админка: staff не может стать суперпользователем; тенант staff — только из профиля; IDOR в кастомных view закрыты.
- Вход через Telegram/GitHub/Google не связывает аккаунты по username/имени.
- CoinGate callback проверяется через API; пустые секреты Telegram/Wallet Pay отклоняются; вебхуки создают только админы.
- Redis с паролем и без публикации порта; debug-эндпоинты удалены; токен бота убран из шаблонов.
- Посты/проекты, сообщения, подтемы ограничены тенантом.
