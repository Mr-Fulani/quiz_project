from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from django.shortcuts import render
from django.contrib.auth.views import LogoutView


# Функция обработки ошибки 404
def custom_404_view(request, exception):
    return render(request, "404.html", status=404)


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


# Обработчик ошибки 404 (должен быть указан **после** `urlpatterns`)
from django.conf.urls import handler404
handler404 = custom_404_view
