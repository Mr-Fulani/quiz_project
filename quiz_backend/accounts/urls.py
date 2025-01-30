from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # Аутентификация
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('register/', views.RegisterView.as_view(), name='register'),
    
    # Профили пользователей
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('profile/update/', views.ProfileUpdateView.as_view(), name='profile-update'),
    path('profile/deactivate/', views.ProfileDeactivateView.as_view(), name='profile-deactivate'),
    
    # Управление подписками
    path('subscriptions/', views.SubscriptionListView.as_view(), name='subscription-list'),
    path('subscriptions/<int:pk>/', views.SubscriptionDetailView.as_view(), name='subscription-detail'),
    
    # Администраторы
    path('admins/', views.AdminListView.as_view(), name='admin-list'),
    path('admins/<int:admin_id>/', views.AdminDetailView.as_view(), name='admin-detail'),
    path('admins/telegram/', views.TelegramAdminListView.as_view(), name='telegram-admin-list'),
    path('admins/django/', views.DjangoAdminListView.as_view(), name='django-admin-list'),
    
    # Статистика
    path('stats/', views.UserStatsView.as_view(), name='user-stats'),
] 