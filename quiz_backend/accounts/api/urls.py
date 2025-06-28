from django.urls import path
from . import views

app_name = 'accounts_api'

urlpatterns = [
    # Аутентификация и токены
    path('token/', views.CustomObtainAuthToken.as_view(), name='token'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('register/', views.RegisterView.as_view(), name='register'),

    # Профили пользователей
    path('profile/update/', views.ProfileUpdateView.as_view(), name='profile-update'),
    path('profile/deactivate/', views.ProfileDeactivateView.as_view(), name='profile-deactivate'),
    path('profile/<int:user_id>/', views.PublicProfileAPIView.as_view(), name='public-profile'),

    # Управление подписками
    path('subscriptions/', views.SubscriptionListView.as_view(), name='subscription-list'),
    path('subscriptions/<int:pk>/', views.SubscriptionDetailView.as_view(), name='subscription-detail'),

    # Администраторы
    path('admins/', views.AdminListView.as_view(), name='admin-list'),
    path('admins/<int:pk>/', views.AdminDetailView.as_view(), name='admin-detail'),
    path('admins/telegram/', views.TelegramAdminListView.as_view(), name='telegram-admin-list'),
    path('admins/django/', views.DjangoAdminListView.as_view(), name='django-admin-list'),

    # Статистика
    path('stats/', views.UserStatsView.as_view(), name='user-stats'),
] 