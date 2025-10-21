from django.urls import path
from . import api_views
from . import mini_app_analytics

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
    path('miniapp-users/update/<int:telegram_id>/', api_views.MiniAppUserUpdateByTelegramIDView.as_view(), name='miniapp-user-update-by-telegram'),
    path('miniapp-users/profile/by-telegram/', api_views.MiniAppProfileByTelegramID.as_view(), name='miniapp-profile-by-telegram'),
    path('miniapp-users/top/', api_views.MiniAppTopUsersListView.as_view(), name='miniapp-top-users'), # Новый эндпоинт для топ-пользователей Mini App
    path('miniapp-users/statistics/', api_views.MiniAppUserStatisticsView.as_view(), name='miniapp-user-statistics'), # Статистика пользователя Mini App
    path('miniapp-users/public-profile/<int:telegram_id>/', api_views.MiniAppUserPublicProfileView.as_view(), name='miniapp-user-public-profile'), # Публичный профиль пользователя Mini App
    path('programming-languages/', api_views.ProgrammingLanguagesListView.as_view(), name='programming-languages'), # Языки программирования для фильтрации
    
    # Аватарки пользователей Mini App
    path('miniapp-users/<int:telegram_id>/avatars/', api_views.UserAvatarUploadView.as_view(), name='miniapp-user-avatar-upload'),
    path('miniapp-users/<int:telegram_id>/avatars/<int:avatar_id>/', api_views.UserAvatarDeleteView.as_view(), name='miniapp-user-avatar-delete'),
    path('miniapp-users/<int:telegram_id>/avatars/reorder/', api_views.UserAvatarReorderView.as_view(), name='miniapp-user-avatar-reorder'),
    
    # Аналитика Mini App (только для админов)
    path('mini-app-analytics/donations/', mini_app_analytics.donations_analytics, name='mini-app-analytics-donations'),
    path('mini-app-analytics/subscriptions/', mini_app_analytics.subscriptions_analytics, name='mini-app-analytics-subscriptions'),
    path('mini-app-analytics/activity/', mini_app_analytics.activity_analytics, name='mini-app-analytics-activity'),
    path('mini-app-analytics/overview/', mini_app_analytics.overview_analytics, name='mini-app-analytics-overview'),
] 