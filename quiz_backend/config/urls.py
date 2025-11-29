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
from blog.views import custom_set_language
from donation.views import (
    create_payment_intent, 
    create_payment_method, 
    confirm_payment, 
    stripe_webhook, 
    get_stripe_publishable_key,
    get_crypto_currencies,
    create_crypto_payment,
    get_crypto_payment_status,
    create_wallet_pay_payment,
    wallet_pay_webhook,
    create_telegram_stars_invoice,
)
from social_auth.views import TelegramAuthView

from blog.sitemaps import ProjectSitemap, PostSitemap, MainPagesSitemap, QuizSitemap, ImageSitemap, SubtopicSitemap, TaskImageSitemap
from django.template.response import TemplateResponse

# Health check endpoint
from django.http import HttpResponse
from django.contrib.sites.shortcuts import get_current_site

def health_check(request):
    return HttpResponse("OK", status=200)

def root_with_verification(request):
    """
    Специальный view для корневой страницы, который отдает HTML с метатегами верификации
    для всех запросов (включая роботов Яндекс Дзен, Яндекс Вебмастер) и делает редирект для пользователей.
    Сохраняет SEO качество используя правильные редиректы.
    """
    from django.conf import settings
    
    # Получаем коды верификации
    yandex_verification = getattr(settings, 'YANDEX_VERIFICATION_CODE', '')
    yandex_zen_verification = getattr(settings, 'YANDEX_ZEN_VERIFICATION_CODE', '')
    
    # Если есть коды верификации, ВСЕГДА отдаем HTML с метатегами на корневой странице
    # Это гарантирует, что роботы Яндекс Дзен и Яндекс Вебмастер увидят метатеги
    if yandex_verification or yandex_zen_verification:
        scheme = 'https' if request.is_secure() else 'http'
        host = request.get_host()
        canonical_url = f"{scheme}://{host}/en/"
        
        # Проверяем User-Agent для определения типа клиента
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        is_bot = any(bot in user_agent for bot in [
            'yandex', 'yandexbot', 'yandexzen', 'googlebot', 'bingbot', 
            'slurp', 'duckduckbot', 'baiduspider', 'facebot', 'ia_archiver',
            'facebookexternalhit', 'twitterbot', 'linkedinbot', 'whatsapp',
            'telegrambot', 'crawler', 'spider', 'bot'
        ])
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>QuizHub - Programming Quizzes & Learning</title>
    <link rel="canonical" href="{canonical_url}">"""
        
        if yandex_verification:
            html += f'\n    <meta name="yandex-verification" content="{yandex_verification}" />'
        
        if yandex_zen_verification:
            html += f'\n    <meta name="zen-verification" content="{yandex_zen_verification}" />'
        
        # Для роботов делаем редирект с задержкой, чтобы они успели прочитать метатеги
        # Для обычных пользователей - быстрый редирект
        delay = '2' if is_bot else '0'
        html += f"""
    <meta http-equiv="refresh" content="{delay}; url={canonical_url}">
    <script>setTimeout(function(){{window.location.href = '{canonical_url}';}}, {delay}000);</script>
</head>
<body>
    <p>Redirecting to <a href="{canonical_url}">main page</a>...</p>
</body>
</html>"""
        
        return HttpResponse(html, content_type='text/html')
    
    # Если кодов верификации нет, используем обычный 301 редирект
    from django.shortcuts import redirect
    return redirect('/en/', permanent=True)

def robots_txt_view(request):
    """
    Генерирует robots.txt динамически с правильным доменом для sitemap.
    """
    current_site = get_current_site(request)
    # Всегда используем HTTPS в продакшене
    scheme = 'https'
    sitemap_url = f"{scheme}://{current_site.domain}/sitemap.xml"
    
    robots_content = f"""User-agent: *
Disallow: /admin/
Disallow: /api/
Disallow: /swagger/
Disallow: /redoc/
Disallow: /messages/
Disallow: /inbox/
Disallow: /silk/
Disallow: /__debug__/
Allow: /

# Sitemap
Sitemap: {sitemap_url}
"""
    return HttpResponse(robots_content, content_type='text/plain')

def custom_sitemap_view(request, sitemaps, section=None, template_name='blog/sitemap.xml', content_type='application/xml'):
    """
    Кастомный view для sitemap, который правильно передает alternates в шаблон.
    """
    from django.contrib.sites.models import Site
    from django.contrib.sitemaps import Sitemap
    
    req_protocol = 'https'
    req_site = get_current_site(request)
    
    if section is not None:
        if section not in sitemaps:
            from django.http import Http404
            raise Http404("No sitemap available for section: %r" % section)
        maps = [sitemaps[section]]
    else:
        maps = sitemaps.values()
    
    try:
        page = int(request.GET.get("p", 1))
    except (TypeError, ValueError):
        page = 1
    
    urls = []
    for site_map in maps:
        try:
            if callable(site_map):
                site_map = site_map()
            # Получаем URL с alternates
            site_urls = site_map.get_urls(page=page, site=req_site, protocol=req_protocol)
            urls.extend(site_urls)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error processing sitemap: {e}")
            continue
    
    return TemplateResponse(
        request, template_name, {'urlset': urls},
        content_type=content_type
    )


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
# ImageSitemap временно исключен - изображения добавляются через PostSitemap и ProjectSitemap
# чтобы избежать дублирования URL и проблем с hreflang
sitemaps = {
    'posts': PostSitemap,
    'projects': ProjectSitemap,
    'main': MainPagesSitemap,
    'quizzes': QuizSitemap,
    'subtopics': SubtopicSitemap,  # Подтемы квизов для индексации
    'task_images': TaskImageSitemap,  # Изображения задач с названиями темы и подтемы
    # 'images': ImageSitemap,  # Временно исключен - дублирует URL из posts/projects
}




urlpatterns = [
    path('i18n/', include('django.conf.urls.i18n')),  # URL для обработки переключения языка
    re_path(r'^admin$', RedirectView.as_view(url='/admin/', permanent=True)), # Редирект для /admin
    path('admin/', admin.site.urls),

    # API endpoints (вне языковых паттернов)
    path('api/', include('platforms.urls')),
    path('api/', include('feedback.urls')),
    path('api/tasks/', include('tasks.urls')),  # Перемещаем tasks.urls в отдельный namespace
    path('api/', include('blog.api.api_urls')),  # Добавляем blog API
    path('api/', include('topics.urls')),  # Перемещаем topics.urls после blog.api.api_urls
    path('api/accounts/', include('accounts.api.api_urls')),  # Добавляем accounts API
    path('api/webhooks/', include('webhooks.urls')),
    path('api/social-auth/', include('social_auth.urls')),  # Добавляем social_auth API
    
    # Debug endpoints (вне языковых паттернов)
    # path('debug/telegram-auth/', include('blog.urls')), # Убираем дублирующее подключение
    
    # Telegram Auth - прямой путь к TelegramAuthView
    path('auth/telegram/', TelegramAuthView.as_view(), name='telegram_auth_direct'),
    
    # Donation API endpoints (вне языковых паттернов)
    path('donation/create-payment-intent/', create_payment_intent, name='create_payment_intent'),
    path('donation/create-payment-method/', create_payment_method, name='create_payment_method'),
    path('donation/confirm-payment/', confirm_payment, name='confirm_payment'),
    path('donation/stripe-webhook/', stripe_webhook, name='stripe_webhook'),
    path('api/stripe-publishable-key/', get_stripe_publishable_key, name='get_stripe_publishable_key'),
    
    # Crypto donation API endpoints
    path('api/donation/crypto-currencies/', get_crypto_currencies, name='api_crypto_currencies'),
    path('api/donation/crypto/create-payment/', create_crypto_payment, name='api_create_crypto_payment'),
    path('api/donation/crypto/status/<str:order_id>/', get_crypto_payment_status, name='api_crypto_payment_status'),
    
    # Wallet Pay donation API endpoints
    path('api/donation/wallet-pay/create-payment/', create_wallet_pay_payment, name='wallet_pay_create'),
    path('api/donation/wallet-pay/webhook/', wallet_pay_webhook, name='wallet_pay_webhook'),
    
    # Telegram Stars donation API endpoints
    path('api/donation/telegram-stars/create-invoice/', create_telegram_stars_invoice, name='api_create_telegram_stars_invoice'),
    
    # Специальный view для корневой страницы с метатегами верификации для роботов
    # Отдает HTML с метатегами для Яндекс Дзен и Яндекс Вебмастер, делает редирект для пользователей
    path('', root_with_verification, name='root-redirect'),
    
    # Редирект для VK sharing - URL без языкового префикса
    # Используем permanent=True (301) для SEO, чтобы поисковики индексировали правильный URL
    path('post/<slug:slug>/', RedirectView.as_view(url='/ru/post/%(slug)s/', permanent=True), name='post_no_lang'),
    path('project/<slug:slug>/', RedirectView.as_view(url='/ru/project/%(slug)s/', permanent=True), name='project_no_lang'),    


    # Кастомный переключатель языка (вне языковых паттернов для работы с любым языком)
    path('set-language/', custom_set_language, name='custom_set_language'),
    path('health/', health_check, name='health_check'),  # Health check endpoint
    
    # SEO файлы (вне языковых паттернов)
    path('robots.txt', robots_txt_view, name='robots_txt'),
    path('sitemap.xml', custom_sitemap_view, {'sitemaps': sitemaps, 'template_name': 'blog/sitemap.xml'}, name='django.contrib.sitemaps.views.sitemap'),
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

handler413 = 'blog.views.custom_413'
# -> Обработчик 413 направлен на функцию custom_413 в blog/views.py

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

