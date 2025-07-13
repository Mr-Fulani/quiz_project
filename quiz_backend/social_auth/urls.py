from django.urls import path
from . import views

app_name = 'social_auth'

urlpatterns = [
    # API endpoints для социальной аутентификации
    path('api/telegram/auth/', views.TelegramAuthView.as_view(), name='telegram_auth_api'),
    path('api/accounts/', views.user_social_accounts, name='user_social_accounts'),
    path('api/accounts/<str:provider>/disconnect/', views.disconnect_social_account, name='disconnect_social_account'),
    path('api/providers/', views.enabled_providers, name='enabled_providers'),
    path('api/status/', views.social_auth_status, name='social_auth_status'),
    
    # Обработчик редиректа для Telegram Login Widget
    path('telegram/auth/', views.telegram_auth_redirect, name='telegram_auth_redirect'),
]
