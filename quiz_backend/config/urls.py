from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.contrib.sitemaps.views import sitemap
from django.contrib.staticfiles.views import serve
from django.shortcuts import render
from django.urls import path, include, re_path
from django.views.static import serve as static_serve
from django.views.decorators.csrf import csrf_exempt
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions
from django.views.generic.base import RedirectView

from blog.api.api_views import tinymce_image_upload
from donation.views import create_payment_intent, create_payment_method, confirm_payment, stripe_webhook
from social_auth.views import TelegramAuthView

from blog.sitemaps import ProjectSitemap, PostSitemap, MainPagesSitemap, QuizSitemap, ImageSitemap


def telegram_test_ping_view(request):
    """Тестовый endpoint для проверки доступности"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.error(f"=== TELEGRAM PING TEST ===")
    logger.error(f"Method: {request.method}")
    logger.error(f"Headers: {dict(request.META)}")
    logger.error(f"Body: {request.body}")
    
    from django.http import JsonResponse
    return JsonResponse({
        'status': 'ok',
        'message': 'Server accessible',
        'method': request.method
    })

# Настройки Swagger
schema_view = get_schema_view(
    openapi.Info(
        title="Quiz API",
        default_version='v1',
        description="API documentation for Quiz project",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="contact@quiz.local"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)


# Карта сайта
sitemaps = {
    'posts': PostSitemap,
    'projects': ProjectSitemap,
    'main': MainPagesSitemap,
    'quizzes': QuizSitemap,
    'images': ImageSitemap,
}




urlpatterns = [
    path('i18n/', include('django.conf.urls.i18n')),  # URL для обработки переключения языка
    re_path(r'^admin$', RedirectView.as_view(url='/admin/', permanent=True)), # Редирект для /admin
    path('admin/', admin.site.urls),

    # API endpoints (вне языковых паттернов)
    path('api/', include('tasks.urls')),
    path('api/', include('topics.urls')),
    path('api/', include('platforms.urls')),
    path('api/', include('feedback.urls')),
    path('api/', include('blog.api.api_urls')),  # Добавляем blog API
    path('api/accounts/', include('accounts.api.api_urls')),  # Добавляем accounts API
    path('api/webhooks/', include('webhooks.urls')),
    path('api/social-auth/', include('social_auth.urls')),  # Добавляем social_auth API
    
    # Debug endpoints (вне языковых паттернов)
    path('debug/telegram-auth/', include('blog.urls')),
    
    # Telegram Auth - прямой путь к TelegramAuthView
    path('auth/telegram/', TelegramAuthView.as_view(), name='telegram_auth_direct'),
    path('telegram/ping/', telegram_test_ping_view, name='telegram_ping'),
    
    # Donation API endpoints (вне языковых паттернов)
    path('donation/create-payment-intent/', create_payment_intent, name='create_payment_intent'),
    path('donation/create-payment-method/', create_payment_method, name='create_payment_method'),
    path('donation/confirm-payment/', confirm_payment, name='confirm_payment'),
    path('donation/stripe-webhook/', stripe_webhook, name='stripe_webhook'),
    
    # Редирект с корневого URL на язык по умолчанию
    path('', RedirectView.as_view(pattern_name='blog:home', permanent=False), name='root-redirect'),

] + i18n_patterns(
    # path('admin/', admin.site.urls), -> Перенесено выше
    #   -> Админ-панель Django

    path('', include('blog.urls')),
    #   -> Основные URL-ы приложения blog (home, about, contact, etc.)

    path('accounts/', include('accounts.urls')),
    #   -> Подключение НАШИХ URL-ов из accounts.urls в первую очередь
    #   -> Это включает кастомную регистрацию, профили и сброс пароля

    # path('social-auth/', include('social_auth.urls')),  # Убираем дублирование - уже подключено в API секции
    #   -> Подключение URL-ов для социальной аутентификации

    path('donation/', include('donation.urls')),
    #   -> Подключение URL-ов из приложения donation (страница пожертвований)

    path('logout/', LogoutView.as_view(next_page='/'), name='logout'),
    #   -> Логаут с редиректом на главную

    # Swagger URLs (документация API)
    path('swagger<format>/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),


    path('tinymce/', include('tinymce.urls')),  # Добавляем маршруты TinyMCE
    path('tinymce/upload/', tinymce_image_upload, name='tinymce_image_upload'),

    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('robots.txt', static_serve, {'document_root': settings.STATIC_ROOT, 'path': 'robots.txt'}),
)

# Подключение статических и медиа-файлов в режиме разработки (DEBUG=True)
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


def test_404(request):
    """
    Пример представления для тестирования 404 (рендерит 404.html).
    """
    return render(request, '404.html')


handler404 = 'blog.views.custom_404'
# -> Обработчик 404 направлен на функцию custom_404 в blog/views.py

# Убрал дублирование, так как static() уже обрабатывает это для DEBUG=True
# Всегда обслуживаем статические файлы (если требуется)
# urlpatterns += [
#     path('static/<path:path>', serve, {'document_root': settings.STATIC_ROOT}),
#     path('404/', test_404, name='404'),  # Пример ссылки на тестовый 404
# ]
urlpatterns += [
    path('404/', test_404, name='404'),  # Пример ссылки на тестовый 404
]



# Debugging and profiling tools
if settings.DEBUG:
    import debug_toolbar
    urlpatterns += [
        path('__debug__/', include(debug_toolbar.urls)),  # django-debug-toolbar
        path('silk/', include('silk.urls', namespace='silk')),  # django-silk
    ]

