from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.contrib.staticfiles.views import serve
from django.shortcuts import render
from django.urls import path, include
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

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

urlpatterns = [
    path('admin/', admin.site.urls),
    #   -> Админ-панель Django

    path('', include('blog.urls')),
    #   -> Основные URL-ы приложения blog (home, about, contact, etc.)

    path('accounts/', include('django.contrib.auth.urls')),
    #   -> Стандартные пути аутентификации (login, logout, password_change, etc.)

    path('users/', include('accounts.urls')),
    #   -> Подключение URL-ов из приложения accounts (регистрация, профили и т.д.)

    path('logout/', LogoutView.as_view(next_page='/'), name='logout'),
    #   -> Логаут с редиректом на главную


    # API для tasks, topics, platforms, feedback, webhooks
    path('api/', include('tasks.urls')),
    path('api/', include('topics.urls')),
    path('api/', include('platforms.urls')),
    path('api/', include('feedback.urls')),
    path('api/webhooks/', include('webhooks.urls')),

    # Swagger URLs (документация API)
    path('swagger<format>/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]

# Подключение статических файлов, если DEBUG=True
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT) \
               + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


def test_404(request):
    """
    Пример представления для тестирования 404 (рендерит 404.html).
    """
    return render(request, '404.html')


handler404 = 'blog.views.custom_404'
# -> Обработчик 404 направлен на функцию custom_404 в blog/views.py

# Всегда обслуживаем статические файлы (если требуется)
urlpatterns += [
    path('static/<path:path>', serve, {'document_root': settings.STATIC_ROOT}),
    path('404/', test_404, name='404'),  # Пример ссылки на тестовый 404
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)