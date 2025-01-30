from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('blog.urls')),  # Главная страница
    path('api/', include('accounts.urls')),
    path('api/', include('tasks.urls')),
    path('api/', include('topics.urls')),
    path('api/', include('platforms.urls')),
    path('api/', include('feedback.urls')),
    path('api/webhooks/', include('webhooks.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
