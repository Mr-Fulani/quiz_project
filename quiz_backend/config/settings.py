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
DEBUG = True



ALLOWED_HOSTS = ['*']

# Настройки django-debug-toolbar
INTERNAL_IPS = [
    '127.0.0.1',
    'localhost',
]


# Application definition

INSTALLED_APPS = [
    # Ваши приложения
    'accounts',

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
    'debug_toolbar',
    'silk',
]

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
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'accounts.middleware.UpdateLastSeenMiddleware',
    'debug_toolbar.middleware.DebugToolbarMiddleware',
    'silk.middleware.SilkyMiddleware',
]

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
        'APP_DIRS': False,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.i18n',
                'blog.context_processors.unread_messages',
                'blog.context_processors.personal_info',
                'blog.context_processors.marquee_text',
                'accounts.context_processors.user_profile',
                'blog.context_processors.unread_messages_count',
                'blog.context_processors.seo_context',
                'blog.context_processors.analytics_context',
            ],
            'loaders': [
                'django.template.loaders.filesystem.Loader',
                'django.template.loaders.app_directories.Loader',
            ],
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
LANGUAGE_CODE = 'en-us'

LOCALE_MIDDLEWARE_IGNORE_ACCEPT_LANGUAGE = True


LOCALE_PATHS = [
    os.path.join(BASE_DIR, 'locale'),
]



# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

STATIC_URL = '/static/'
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

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
        'rest_framework.permissions.IsAuthenticated',
    ],
}

# Настройки безопасности
# settings.py
CSRF_COOKIE_SECURE = False  # Для HTTP
CSRF_COOKIE_HTTPONLY = False
CSRF_USE_SESSIONS = False
CSRF_COOKIE_SAMESITE = 'Lax'

SESSION_COOKIE_SECURE = False  # Для HTTP
SESSION_COOKIE_SAMESITE = 'Lax'

# Разрешаем CSRF для конкретных доменов
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:8001',
    'http://127.0.0.1:8001',
]

# CORS настройки
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = [
    "http://localhost:8001",
    "http://127.0.0.1:8001",
]

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

# CORS настройки
CORS_ALLOW_ALL_ORIGINS = True  # Только для разработки!
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^http://localhost:8001$",
]
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
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}



# EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'  # Для разработки
# EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'


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


