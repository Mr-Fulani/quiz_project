from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from django.shortcuts import render, redirect
from django.contrib.auth.views import LogoutView
from django.conf.urls import handler404
from blog.views import custom_404  # создадим этот view
from django.views import defaults as default_views
from django.contrib.staticfiles.views import serve




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


# Основной список URL-ов
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('blog.urls')),  # Основные URL
    path('accounts/', include('django.contrib.auth.urls')),  # стандартные auth URLs
    path('users/', include('accounts.urls')),  # убрали namespace
    path('logout/', LogoutView.as_view(next_page='/'), name='logout'),
    path('api/', include('tasks.urls')),
    path('api/', include('topics.urls')),
    path('api/', include('platforms.urls')),
    path('api/', include('feedback.urls')),
    path('api/webhooks/', include('webhooks.urls')),
    
    # Swagger URLs
    path('swagger<format>/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT) \
  + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


def test_404(request):
    return render(request, '404.html')

handler404 = 'blog.views.custom_404'

# Всегда обслуживаем статические файлы
urlpatterns += [
    path('static/<path:path>', serve, {'document_root': settings.STATIC_ROOT}),
    path('404/', test_404, name='404'),  # Добавляем реальный view
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
