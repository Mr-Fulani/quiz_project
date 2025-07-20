from django.urls import path
from . import api_views

app_name = 'accounts_api'

urlpatterns = [
    # Аутентификация и токены
    path('token/', api_views.CustomObtainAuthToken.as_view(), name='token'),
    path('login/', api_views.LoginView.as_view(), name='login'),
    path('register/', api_views.RegisterView.as_view(), name='register'),

    # Профили пользователей
    path('profile/', api_views.PublicProfileAPIView.as_view(), name='profile'),
    path('profile/update/', api_views.ProfileUpdateView.as_view(), name='profile-update'),
    path('profile/deactivate/', api_views.ProfileDeactivateView.as_view(), name='profile-deactivate'),
    path('profile/<int:user_id>/', api_views.PublicProfileAPIView.as_view(), name='public-profile'),
    path('profile/by-telegram/', api_views.ProfileByTelegramID.as_view(), name='public-profile-by-telegram'),
    path('profile/by-telegram/<int:telegram_id>/', api_views.PublicProfileByTelegramAPIView.as_view(), name='get-profile-by-telegram'),
    path('profile/by-telegram/<int:telegram_id>/update/', api_views.ProfileUpdateByTelegramView.as_view(), name='profile-update-by-telegram'),

    # Управление подписками
    path('subscriptions/', api_views.SubscriptionListView.as_view(), name='subscription-list'),
    path('subscriptions/<int:pk>/', api_views.SubscriptionDetailView.as_view(), name='subscription-detail'),

    # Администраторы
    path('admins/', api_views.AdminListView.as_view(), name='admin-list'),
    path('admins/<int:pk>/', api_views.AdminDetailView.as_view(), name='admin-detail'),
    path('admins/telegram/', api_views.TelegramAdminListView.as_view(), name='telegram-admin-list'),
    path('admins/django/', api_views.DjangoAdminListView.as_view(), name='django-admin-list'),

    # Статистика
    path('stats/', api_views.UserStatsView.as_view(), name='user-stats'),
    
    # Mini App пользователи
    path('miniapp-users/', api_views.MiniAppUserViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='miniapp-user-list'),
    path('miniapp-users/me/', api_views.MiniAppUserViewSet.as_view({
        'get': 'me'
    }), name='miniapp-user-me'),
    path('miniapp-users/update-last-seen/', api_views.MiniAppUserViewSet.as_view({
        'post': 'update_last_seen'
    }), name='miniapp-user-update-last-seen'),
    path('miniapp-users/link-users/', api_views.MiniAppUserViewSet.as_view({
        'post': 'link_users'
    }), name='miniapp-user-link-users'),
    path('miniapp-users/<int:pk>/', api_views.MiniAppUserViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='miniapp-user-detail'),
    path('miniapp-users/by-telegram/<int:telegram_id>/', api_views.MiniAppUserByTelegramIDView.as_view(), name='miniapp-user-by-telegram'),
] 