from django.urls import path
from . import views

app_name = 'social_auth'

urlpatterns = [
    # API endpoints для социальной аутентификации
    # Добавляем оба варианта (с trailing slash и без) для совместимости
    path('telegram/auth/', views.TelegramAuthView.as_view(), name='telegram_auth_api'),
    path('telegram/auth', views.TelegramAuthView.as_view(), name='telegram_auth_api_no_slash'),  # Без trailing slash
    path('telegram/auth/debug/', views.telegram_auth_debug, name='telegram_auth_debug'),  # Временный debug endpoint
    path('telegram/auth/debug', views.telegram_auth_debug, name='telegram_auth_debug_no_slash'),  # Без trailing slash
    path('telegram/oauth/', views.telegram_oauth_redirect, name='telegram_oauth_redirect'),
    path('telegram/callback/', views.TelegramAuthCallbackView.as_view(), name='telegram_callback'),
    path('telegram/callback', views.TelegramAuthCallbackView.as_view(), name='telegram_callback_no_slash'),  # Без trailing slash
    
    # GitHub OAuth endpoints
    path('github/oauth/', views.github_auth_redirect, name='github_oauth_redirect'),
    path('github/callback/', views.GitHubAuthCallbackView.as_view(), name='github_callback'),
    path('github/callback', views.GitHubAuthCallbackView.as_view(), name='github_callback_no_slash'),  # Без trailing slash
    
    path('accounts/', views.user_social_accounts, name='user_social_accounts'),
    path('accounts/<str:provider>/disconnect/', views.disconnect_social_account, name='disconnect_social_account'),
    path('providers/', views.enabled_providers, name='enabled_providers'),
    path('status/', views.social_auth_status, name='social_auth_status'),
    

]
