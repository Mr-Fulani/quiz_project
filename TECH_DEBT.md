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
- [ ] 🟠 Боты тенантов: у каждого реального тенанта (it-dev и quiz-code на новом домене) заполнить в админке
      `bot_token` (свой бот из @BotFather) и `mini_app_domain`; тестовые тенанты (quiz-format, quiz-game) —
      выключить (`is_active=False`), иначе бот попытается запустить и их. Если какой-то тенант остаётся на
      глобальном `TELEGRAM_BOT_TOKEN` — указать его в `BOT_DEFAULT_TENANT_SLUG`. Затем перезапустить бота.
      Каждый бот тенанта должен быть админом в каналах своего тенанта (для публикации).
- [ ] 🟠 Привязать старые записи без тенанта: `python manage.py assign_tenant_to_legacy_rows --slug <тенант>`
      (сначала без `--apply` — посмотреть отчёт). До этого они видны всем тенантам как общие.
- [ ] 🟡 Порты 8001/8080/5433/8002 теперь только на `127.0.0.1`. Если вы ходили в админку/API по `IP:8001`
      снаружи — это больше не работает (используйте домен или SSH-туннель).
- [ ] 🟡 Решить, нужен ли `SOCIAL_MEDIA_CALLBACK_SECRET` для Make.com (и прописать заголовок в сценарии).
- [ ] 🟡 Подтвердить: Mini App в обычном браузере (без Telegram) теперь только читает — запись требует initData.
- [ ] 🟢 Прогнать `tasks/tests` и `topics/tests` в Docker. На SQLite падают (не из-за изменений аудита):
      `test_normalize_subtopics` — уникальный индекс `(topic, name)`; 3 теста `test_task_import` — регистр
      кириллицы (`lower()` в SQLite только для ASCII), на Postgres, вероятно, проходят;
      `test_generate_islamic_image` — тест передаёт `tenant_slug`, которого у `generate_image_for_task` нет (устарел).
- [ ] 🟠 При деплое выполнить миграции (`blog 0034` — новый `upload_to` вложений) и `collectstatic`
      (изменён `quiz_styles.css`), перезагрузить nginx (новые location для вложений).
- [ ] 🟡 Перед `git rm --cached media/ staticfiles/` (см. «Мёртвый код») — решить, как деплоите: если сервер
      делает `git pull` в рабочую копию с `./media`, удаление из индекса **удалит эти файлы на сервере** при pull.
      Сначала сделать бэкап `media/` или перенести медиа вне репозитория.

---

## 🔐 Безопасность и изоляция данных

### Mini App
- [ ] 🟢 `mini_app/routers/pages.py` всё ещё передаёт в Django `telegram_id` из cookie/`X-Telegram-User-Id` —
      безопасно (Django учитывает его только при совпадении с подписью), но можно брать id из проверенного
      пользователя. `pages.py` `update_profile` — пустая заглушка.
- [ ] 🟡 `LanguageMiddleware` меняет язык на глобальном синглтоне `localization_service` — гонка между
      запросами (пользователь может получить чужой язык).
- [ ] 🟢 Логи mini_app пишут полные профили и заголовки запросов (PII).

### Бот и Celery
- [ ] 🟡 Видео для админа (`video_generation_service` → `TELEGRAM_ADMIN_CHAT_ID`) и `feedback/services.py`
      шлют глобальным ботом — проверить, нужен ли бот тенанта.
- [ ] 🟢 Бот при каждом старте вызывает `Base.metadata.create_all` по общей БД Django — лишнее, таблицы
      создаёт Django.
- [ ] 🟡 Вебхуки, ссылки, credentials соцсетей с `tenant=NULL` считаются **общими** для всех тенантов
      (`tenants/scoping.py`) — чтобы не сломать текущую публикацию. Проставьте `tenant` в админке у записей,
      которые относятся к одному сайту. `DefaultLink` (unique `language, topic`) и `MainFallbackLink`
      (unique `language`) глобально уникальны — для своих ссылок у разных тенантов нужна миграция на
      `UniqueConstraint(tenant, …)`.
- [ ] 🟡 ~44 места ищут `MiniAppUser` по `telegram_id` без тенанта (`tasks/comment_views.py`,
      `tasks/notification_service.py`, …): `.get()` даст MultipleObjectsReturned, `.first()` — чужой профиль.
- [ ] 🟡 Аналитика Mini App (`accounts/api/mini_app_analytics.py`) считает донаты/подписки/активность
      по всем тенантам (доступ уже ограничен админом тенанта).
- [ ] 🟡 Письма с формы контактов уходят на глобальный `EMAIL_ADMIN`, а не `tenant.contact_email`.

### Django
- [ ] 🟠 Вход не привязан к тенанту: `CustomUser.username` уникален глобально, логин тенанта A работает на B.
      Нужен tenant-aware backend + `UniqueConstraint(tenant, username)` (миграция данных).
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

- [ ] 🟠 mini_app вызывает `/api/subtopics/<id>/` дважды за загрузку страницы задач
      (`mini_app/routers/pages.py` `get_subtopic_detail` и `get_tasks_for_subtopic`); первый вызов без `level`
      грузит все задачи подтемы и почти выбрасывается. (N+1 внутри самого эндпоинта исправлен.)
- [ ] 🟠 `config/settings_production.py` нигде не подключается — Redis-кэш и прочее оттуда в проде не действуют.
      Решить: удалить или подключить.
- [ ] 🟠 `mini_app/templates/base.html`: ~1400 строк inline JS, Stripe/QR/ionicons синхронно на всех страницах.
- [ ] 🟠 `blog/static/blog/js/font-awesome.min.js` (1.5 МБ) на каждой странице вместе с CSS-версией;
      highlight.js и GSAP глобально.
- [ ] 🟡 Новый `httpx.AsyncClient` на каждый запрос в mini_app и логирование всего ответа Django.
- [ ] 🟡 Логи INFO с `=== DEBUG` на каждый запрос; `echo=True` у SQLAlchemy в боте.
- [ ] 🟡 Индексы: `Task.translation_group_id`, `TaskTranslation(task, language)`, `Task(subtopic, difficulty)`.
- [ ] 🟡 `TenantMiddleware`: промахи не кэшируются; кэш перенести в Redis с TTL.
- [ ] 🟢 `WHITENOISE_AUTOREFRESH=True` в проде; `CONN_HEALTH_CHECKS` не включён.

## 🔎 SEO

- [ ] 🟡 `quiz_subtopic.html` добавляет второй viewport с `user-scalable=no` (минус доступности).
- [ ] 🟠 Fuzzy-поиск тем/подтем (`iregex`) плодит дубли URL; пустые страницы отдают 200 (soft 404);
      `difficulty` принимает любое значение.
- [ ] 🟠 Slug без транслитерации (`slugify` по кириллице даёт пустой slug).
- [ ] 🟠 Захардкоженные/одинаковые title («QuizHub», «Quiz Python, Go…» на всех тенантах).
- [ ] 🟠 hreflang для постов без переводов.
- [ ] 🟡 JSON-LD: breadcrumbs выводятся как Python-dict, SearchAction на несуществующий поиск, `logo.png` 404,
      дублирующиеся Article/BlogPosting.
- [ ] 🟡 Mini App: `X-Robots-Tag: noindex` в nginx, share-страницы с `index,follow`.
- [ ] 🟢 Корень `/` отдаёт 200 с meta-refresh вместо 301/302.

## 🗂 Админка

- [ ] 🟠 Нельзя создать задачу сразу на N языках; `translation_group_id` readonly; инлайн перевода без `max_num=1`.
- [ ] 🟠 JSON-импорт генерирует картинки и (с галочкой «Опубликовать») публикует в Telegram синхронно
      в запросе — на больших файлах 504. Экшены списка задач уже в Celery (`tasks/tasks.py`).
- [ ] 🟡 Ссылка «Комментарий #N» ведёт на незарегистрированный `TaskComment` (404).
- [ ] 🟡 `topics/admin.py`: превью через удалённый `allow_tags` (сырой HTML), счётчики N+1.
- [ ] 🟡 `TenantFilteredAdminMixin` добавляет суперпользователю колонку `tenant` — в админках без
      `select_related('tenant')` это запрос на каждую строку (в задачах исправлено).
- [ ] 🟡 `autocomplete_fields` нигде; у задачи тема/подтема — raw_id.
- [ ] 🟡 Возврат Stars, смена статуса доната без подтверждения; `amount`/`status` редактируемы.
- [ ] 🟡 JSON-импорт: нет dry-run, проверки дублей, атомарности; сотни плашек сообщений.
- [ ] 🟢 `LANGUAGE_CODE='en'`, не задан `site_header`; 52 модели в индексе без группировки.
- [ ] 🟢 Бот-админка: удаление без подтверждения, нет `/cancel` в FSM.

## 🧹 Мёртвый код и мусор в репозитории

- [ ] 🟠 В git: `node_modules/` (6667 файлов, удаление не закоммичено), `quiz_backend/staticfiles/` (1916),
      пользовательские `media/` (~300), `.coverage`, egg-info, `postEvent`, `temp_ru.po`, `project_tree.txt`.
      Сделать `git rm --cached` отдельным коммитом и дополнить `.gitignore`.
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

## 🌐 Домены и привязки к проектам

Как сменить домен сайта: в админке поменять `domain`/`mini_app_domain` тенанта (CORS/CSRF и ссылки
подхватят сами), затем nginx (`server_name`, сертификаты) и при необходимости `ALLOWED_HOSTS` в `.env`.
Как сменить домен хранилища: `R2_PUBLIC_DOMAIN` в `.env` + старый домен в `STORAGE_LEGACY_DOMAINS`;
данные в БД не трогать (там ключи файлов).

- [ ] 🟠 Mini App и бот: хардкод бота и бренда — `t.me/mr_proger_bot/quiz` (`mini_app/routers/pages.py`,
      `static/js/share-topic.js`, `templates/profile.html`), «QUIZ-CODE» в приветствии (`profile.html`,
      `services/localization.py`), тестовый telegram_id 975113235 / мок Mr_Fulani (`templates/base.html`,
      `static/js/tasks.js`); в боте fallback-ссылки `t.me/tyt_python`/`t.me/proger_dude`
      (`bot/services/default_link_service.py`, `task_service.py`, `handlers/admin_menu.py`).
      Полный список с номерами строк — в заметках сессии (hardcode-audit-2026-10-19.md).
- [ ] 🟢 Значения по умолчанию инфраструктуры с именами проекта: `R2_BUCKET_NAME='quiz-hub-prod'`
      (`config/settings.py`, `bot/config.py`), `DB_NAME=fulani_quiz_db` (`bot/entrypoint.sh`). Убирать только
      после проверки, что на сервере эти переменные заданы в `.env`, иначе сломается хранилище/БД.
- [ ] 🟢 Моки с личным telegram_id 975113235 (`social_auth/views.py`, `blog/templates/blog/telegram_mock.html`),
      `anonymous@quizproject.com` в `blog/views.py`; упоминания `mr_proger_bot`/`mr_fulani` в документации
      (`SERVER_INSTRUCTIONS.md`, `markdown_post.md`, `PINTEREST_DATA_FORMAT.md`).
- [ ] 🟡 `nginx/nginx-prod.conf` перечисляет домены (`server_name`, пути сертификатов) — при смене домена
      править вручную; `quiz-code.com` и мёртвые quiz-format/quiz-game можно убрать.
- [ ] 🟢 `TENANT_SLUG` в `docker-compose.yml` нигде не читается.

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
- Бот: админ-меню (`admin_menu.py`) и админские хендлеры обратной связи закрыты `IsAdminFilter`;
  `is_admin` учитывает `is_active` и не падает на дублях.
- SEO: canonical/og:url/hreflang — текущая страница, а не главная; www-редирект nginx на свой домен.
- Админка: картинка ответа на обратную связь больше не дублируется; пост с медиа уходит во все каналы.
- Производительность: `subtopic_detail_simple` — фиксированное число запросов вместо 2 на задачу
  (и статистика пользователя ищется в его тенанте).

## ✅ Сделано (2026-10-19)

- Привязки по slug тенанта убраны: стиль картинок и общий логотип — поля `Tenant` (`image_theme`,
  `use_global_logo`, миграция `tenants/0004`); автор, телефон и соцсети в SEO/JSON-LD — из «Данных владельца».
- Личные данные убраны из кода: встроенный профиль (сайдбар, тексты главной/«обо мне», ресурсы) перенесён
  миграцией `blog/0036` в «Данные владельца»/«Ресурсы платформы» quiz-code; SEO-тексты резюме/«обо мне»/контактов
  строятся из имени и профессии владельца; письма (донат, сброс пароля) берут название, email поддержки и соцсети
  из тенанта; резюме — без данных по умолчанию, `import_resume` читает JSON.
- Бренд «QuizHub»/«Quiz Project» в шаблонах, OG-картинках и заголовках заменён названием сайта тенанта;
  GTM — поле тенанта (миграция `tenants/0005` перенесла действовавший ID); бот — `tenant.bot_username`;
  `EMAIL_ADMIN` из `.env`.

- Исходящие вебхуки, `GlobalWebhookLink`, `DefaultLink`/`MainFallbackLink`, credentials соцсетей —
  только тенанта задачи (+ общие без тенанта); сводная отправка разбивается по тенантам.
- «Отправить пост» в админке каналов: только каналы и подписчики бота своего тенанта, нужно право на изменение.
- Вложения личных сообщений: прямой путь в nginx закрыт, раздача через `download_attachment` + X-Accel-Redirect,
  случайные имена файлов, корректный `Content-Disposition`, доступ — участникам, staff тенанта, суперпользователю.
- Подтемы темы в mini_app: статистика тремя запросами на весь список вместо ~13 на подтему.
- Топ пользователей: рейтинг/статистика аннотациями, без запросов на пользователя; фильтр по технологии больше
  не завышает рейтинг; дата рождения приватных профилей скрыта.
- SEO: текст вопроса квиза в HTML, alt картинки из вопроса.
- Mini App: приватное чтение (профиль, статистика, `me`) только с подписью initData; список пользователей —
  админам; прогресс в темах/задачах — только для подписанного пользователя; серверный рендер получает подпись
  из httpOnly-cookie `tg_init_data`.
- Картинки обращений в поддержку и ответов на них — только staff своего тенанта (X-Accel-Redirect);
  общий хелпер `config/protected_media.py`. Картинки комментариев остаются публичными (комментарии публичны).
- Бот: один процесс запускает ботов всех тенантов; все ORM-запросы бота автоматически ограничены тенантом бота
  (`bot/tenancy.py`), новые записи получают тенант. Команда `assign_tenant_to_legacy_rows` для старых записей.
- Django/Celery: публикация, удаление сообщений, рассылка, назначение админов, уведомления, возврат Stars —
  ботом тенанта (`tenants/scoping.bot_token_for`).
- Удалена заглушка Telegram-вебхука в Django (`/api/webhooks/telegram/`): её `setWebhook` отключил бы polling бота.
- SEO постов снова работает: `dynamic_seo_context` падал на `connection.close()` без импорта и молча отдавал
  пустые meta; теперь фильтрует пост/проект по тенанту, имя сайта — из тенанта.
- `personal_info` (на каждой странице сайта) кэшируется на 5 минут по тенанту/языку, сбрасывается при изменении
  `TenantInfo`/`PlatformResource`; убраны отладочные логи.
- Mini App: JS/CSS кэшируются браузером — версия в URL = хэш файла (раньше текущее время), nginx отдаёт `/static/`
  с `?v` как immutable на год.
- Админка задач: колонка с текстом вопроса, поиск по тексту вопроса; список без запросов на каждую строку.
- SEO: `sitemap.xml` и `robots.txt` — домен тенанта из запроса (было: `Site #1` для всех) и только его объекты;
  `Disallow` с языковыми префиксами (`/ru/swagger/`, `/en/inbox/`…); `noindex` на профилях, статистике,
  личных сообщениях, чате, сбросе пароля (`NOINDEX_URL_NAMES` в `blog/context_processors.py`).
- Проверено: правило `.gitignore` `*/migrations/*.py` действует только на каталоги верхнего уровня
  (`backups/migrations`), миграции приложений `quiz_backend/*/migrations/` в git попадают — пункт снят.
- Админка задач: публикация в Telegram (с генерацией недостающих картинок, паузами 3–6 с между задачами,
  вебхуками/видео после), публикация в соцсети и генерация картинок — в Celery (`tasks/tasks.py`, очередь
  `celery`); экшен только ставит задачу в очередь, результат — в полях задач и логах воркера. Больше нет 504.
