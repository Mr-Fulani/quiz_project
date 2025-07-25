import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from django.conf.global_settings import TEMPLATES as DEFAULT_TEMPLATES
import logging



load_dotenv()
logger = logging.getLogger(__name__)


# Отладка загрузки .env
logger.info(f"dotenv loaded: {os.getenv('EMAIL_HOST_USER')}")
logger.info(f"SECRET_KEY: {os.getenv('SECRET_KEY')}")


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Добавляем путь к приложениям в PYTHONPATH
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR.parent))  # добавляем родительскую директорию

# Добавим обратно кастомную модель пользователя
AUTH_USER_MODEL = 'accounts.CustomUser'

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'False') == 'True'

if not DEBUG and not SECRET_KEY:
    logger.critical("SECRET_KEY is not set for production environment!")
    # В продакшене лучше выбросить исключение, чтобы предотвратить запуск с небезопасной конфигурацией
    raise ValueError("SECRET_KEY is not set for production environment!")


# Отключаем проверку хостов для разработки
USE_L10N = False

# Мок для Telegram авторизации в режиме разработки
MOCK_TELEGRAM_AUTH = DEBUG

if DEBUG:
    ALLOWED_HOSTS = ["*", "quiz_backend", "quiz_backend:8000"]
else:
    # Хосты для продакшена - твои домены + localhost для curl
    env_hosts = os.getenv("ALLOWED_HOSTS", "")
    if env_hosts:
        ALLOWED_HOSTS = [h.strip() for h in env_hosts.split(",") if h.strip()]
        # Добавляем localhost для API тестирования
        if 'localhost' not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append('localhost')
        # Добавляем внутренние хосты контейнеров
        if 'quiz_backend' not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append('quiz_backend')
        if 'quiz_backend:8000' not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append('quiz_backend:8000')
        logger.info(f"ALLOWED_HOSTS from env: {ALLOWED_HOSTS}")
    else:
        # Фоллбэк только с твоими хостами
        ALLOWED_HOSTS = [
            'quiz-code.com',
            'www.quiz-code.com',
            'mini.quiz-code.com',
            'localhost',
            '45.14.247.175',  # IP-адрес сервера
            'quiz_backend',   # Внутренний хост контейнера
            'quiz_backend:8000'  # Внутренний хост контейнера с портом
        ]
        logger.warning(f"ALLOWED_HOSTS env var not found, using fallback: {ALLOWED_HOSTS}")

# Добавляем хост ngrok для локальной разработки и тестирования
NGROK_HOST = os.getenv('NGROK_HOST')
if NGROK_HOST:
    ALLOWED_HOSTS.append(NGROK_HOST)

# Настройки для работы за прокси-сервером (Nginx)
CSRF_TRUSTED_ORIGINS = [
    'https://quiz-code.com',
    'https://www.quiz-code.com',
    'https://mini.quiz-code.com',
]
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Настройки django-debug-toolbar
INTERNAL_IPS = [
    '127.0.0.1',
    'localhost',
]


# Application definition

INSTALLED_APPS = [
    # Ваши приложения
    'accounts',
    'donation',
    'social_auth',

    # REST framework
    'rest_framework',
    'rest_framework.authtoken',

    # Системные приложения Django
    'django.contrib.auth',
    'django.contrib.admin',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
    'django.contrib.sites',
    'tasks',
    'topics',
    'feedback',
    'webhooks',
    'platforms',
    'django_filters',
    'drf_yasg',
    'corsheaders',
    'blog.apps.BlogConfig',
    'django.contrib.humanize',
    'tinymce',
    'imagekit',
]

if DEBUG:
    INSTALLED_APPS.extend([
        'debug_toolbar',
        'silk',
    ])

TINYMCE_DEFAULT_CONFIG = {
    'height': 400,
    'width': '100%',
    'plugins': 'advlist autolink lists link image charmap print preview anchor searchreplace visualblocks code fullscreen insertdatetime media table paste code help wordcount',
    'toolbar': 'undo redo | formatselect | bold italic underline strikethrough | alignleft aligncenter alignright alignjustify | bullist numlist outdent indent | link image media | code | help',
    'menubar': 'file edit view insert format tools table help',
    'content_style': 'body { font-family: Arial, sans-serif; font-size: 16px; }',
    'image_advtab': True,
    'file_picker_types': 'file image media',
    'automatic_uploads': True,
    'images_upload_url': '/tinymce/upload/',
    'relative_urls': False,
    'remove_script_host': False,
    'convert_urls': True,
    'image_dimensions': False,  # Отключаем фиксированные размеры
    # Настройки для вставки
    'paste_retain_style_properties': 'color font-size font-weight text-decoration',
    'paste_data_images': True,
    'paste_preprocess': """function (pl, o) {
        // Очистка нежелательных тегов, стилей и размеров
        o.content = o.content.replace(/style="[^"]*"/g, '');
        o.content = o.content.replace(/width="[^"]*"/g, '');
        o.content = o.content.replace(/height="[^"]*"/g, '');
        // Сохранение ссылок и эмодзи
        o.content = o.content.replace(/<a /g, '<a target="_blank" ');
    }""",
}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'config.middleware.RequestLoggingMiddleware',  # Добавляем логирование
    'config.middleware.DisableCSRFForAPI',  # ПЕРЕД CommonMiddleware!
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',  # Возвращаем обратно
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'accounts.middleware.UpdateLastSeenMiddleware',
]

if DEBUG:
    # Добавляем middleware для разработки
    # AllowAllHostsMiddleware можно использовать, если ALLOWED_HOSTS = ['*'] не подходит
    # В данном случае, мы используем '*', так что этот middleware можно закомментировать или удалить
    # MIDDLEWARE.insert(0, 'config.middleware.AllowAllHostsMiddleware')
    MIDDLEWARE.extend([
        'debug_toolbar.middleware.DebugToolbarMiddleware',
        'silk.middleware.SilkyMiddleware',
    ])

ROOT_URLCONF = 'config.urls'


# Настройки django-silk
SILKY_PYTHON_PROFILER = True
SILKY_AUTHENTICATION = True
SILKY_AUTHORISATION = True
SILKY_PERMISSIONS = lambda user: user.is_superuser


TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.i18n',
                'blog.context_processors.unread_messages_count',
                'blog.context_processors.user_statistics',
                'blog.context_processors.personal_info',
                'blog.context_processors.marquee_text',
                'accounts.context_processors.user_profile',
                'blog.context_processors.seo_context',
                'blog.context_processors.dynamic_seo_context',  # НОВЫЙ SEO контекст!
                'blog.context_processors.analytics_context',
                'blog.context_processors.telegram_settings',  # Telegram настройки
            ],
            # 'loaders': [
            #     'django.template.loaders.filesystem.Loader',
            #     'django.template.loaders.app_directories.Loader',
            # ],
        },
    },
]


WSGI_APPLICATION = 'config.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': os.getenv('DATABASE_ENGINE', 'django.db.backends.postgresql'),
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST', 'postgres_db'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGES = (
    ('ru', 'Русский'),
    ('en', 'English'),
)


TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# LANGUAGE_CODE = 'ru-RU'
LANGUAGE_CODE = 'en'

LOCALE_MIDDLEWARE_IGNORE_ACCEPT_LANGUAGE = True


LOCALE_PATHS = [
    os.path.join(BASE_DIR, 'locale'),
]



# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

STATIC_URL = '/static/'

STATICFILES_DIRS = [
    # Только общие файлы, папки приложений обрабатываются автоматически
    os.path.join(BASE_DIR, 'static'),  # Общие файлы
]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Стандартное хранение статических файлов без хеширования
# STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Настройки DRF
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',  # Разрешаем доступ без токена
    ],
}

# Настройки безопасности
if DEBUG:
    CSRF_COOKIE_SECURE = False
    SESSION_COOKIE_SECURE = False
    CSRF_TRUSTED_ORIGINS = [
        'http://localhost:8001',
        'http://127.0.0.1:8001',
        'http://quiz_backend:8000',
        'http://quiz_backend:8001',
        'http://localhost:8080',
    ]
    CORS_ALLOW_ALL_ORIGINS = True
    CORS_ALLOW_CREDENTIALS = True
else:
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    # Для продакшена лучше указать конкретные доверенные источники
    CSRF_TRUSTED_ORIGINS = os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',')
    CORS_ALLOW_ALL_ORIGINS = False
    CORS_ALLOWED_ORIGINS = [
        'https://oauth.telegram.org',
        'https://telegram.org',
        'https://core.telegram.org'
    ] + [o.strip() for o in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()]
    CORS_ALLOW_CREDENTIALS = True # или False, в зависимости от ваших нужд
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 2592000  # 30 дней
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    # Настройки для работы за прокси-сервером (Nginx)
    USE_X_FORWARDED_HOST = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Отключаем CSRF для API endpoints (не рекомендуется для продакшена без должной аутентификации)
CSRF_EXEMPT_PATHS = [
    '/api/',
    '/auth/telegram/',
    '/telegram/',
]

CSRF_COOKIE_HTTPONLY = False
CSRF_USE_SESSIONS = False
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SAMESITE = 'Lax'






# Настройки Swagger/OpenAPI
SWAGGER_SETTINGS = {
    'SECURITY_DEFINITIONS': {
        'Bearer': {
            'type': 'apiKey',
            'name': 'Authorization',
            'in': 'header'
        }
    },
    'USE_SESSION_AUTH': False,
    'JSON_EDITOR': True,
}

# CORS настройки дублируются - убираем дубли
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]


# Authentication settings
LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}



# EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'  # Для разработки
# Временно включаем email для тестирования
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
# if DEBUG:
#     EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
# else:
#     EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'


EMAIL_HOST = os.getenv('EMAIL_HOST')
EMAIL_PORT = os.getenv('EMAIL_PORT')
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
EMAIL_USE_SSL = True
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL')
SERVER_EMAIL = os.getenv('SERVER_EMAIL')
EMAIL_ADMIN = ['fulani.dev@gmail.com']
# EMAIL_ADMIN = [os.getenv('SERVER_EMAIL')]






# Analytics settings
GOOGLE_ANALYTICS_PROPERTY_ID = os.getenv('GOOGLE_ANALYTICS_ID', '')
YANDEX_METRICA_ID = os.getenv('YANDEX_METRICA_ID', '')  # Замените на ваш ID

# Отключение аналитики на локальном сервере (опционально)
ANALYTICAL_INTERNAL_IPS = ['127.0.0.1', 'localhost']

# Stripe настройки
STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY', 'pk_test_...')  # Тестовый ключ
STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY', 'sk_test_...')  # Тестовый ключ
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', 'whsec_...')  # Для webhook









# Site Framework Configuration
SITE_ID = 1

# SEO and Social Media Settings
DEFAULT_OG_IMAGE = '/static/blog/images/default-og-image.jpeg'
DEFAULT_OG_IMAGE_WIDTH = 1200
DEFAULT_OG_IMAGE_HEIGHT = 630

# Site Information
SITE_NAME = 'QUIZ-CODE'
SITE_DESCRIPTION = 'Master programming with interactive quizzes in Python, JavaScript, Go, Java, C#'
SITE_URL = 'https://quiz-code.com'

# Social Media Handles (замените на ваши реальные)
TWITTER_HANDLE = '@quiz_code_hub'
TWITTER_CREATOR = '@mr_fulani'

# SEO Settings
DEFAULT_META_DESCRIPTION = 'Master programming with interactive quizzes and tutorials. Learn Python, JavaScript, Go, Java, C# through practical coding challenges.'
DEFAULT_META_KEYWORDS = 'programming quiz, coding challenges, Python tutorial, JavaScript learning, programming education'

# Telegram Settings
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_BOT_USERNAME = os.getenv('TELEGRAM_BOT_USERNAME', 'mr_proger_bot')
TELEGRAM_WEBHOOK_SECRET = os.getenv('TELEGRAM_WEBHOOK_SECRET', '')

# Social Auth Settings
SOCIAL_AUTH_TELEGRAM_ENABLED = True
SOCIAL_AUTH_TELEGRAM_BOT_NAME = os.getenv('TELEGRAM_BOT_USERNAME', 'mr_proger_bot')








