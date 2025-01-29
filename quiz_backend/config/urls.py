from django.contrib import admin
from django.urls import path, include
from rest_framework.authtoken.views import obtain_auth_token

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/accounts/', include('accounts.urls')),
    # Временно закомментируем остальные URLs
    # path('api/tasks/', include('tasks.urls')),
    # path('api/topics/', include('topics.urls')),
    # path('api/feedback/', include('feedback.urls')),
    # path('api/webhooks/', include('webhooks.urls')),
    # path('api/platforms/', include('platforms.urls')),
    
    # URLs для browsable API
    path('api-auth/', include('rest_framework.urls')),
    path('api-token-auth/', obtain_auth_token),
]
