from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'accounts'

urlpatterns = [
    path('register/', views.register, name='register'),
    # Аутентификация
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),
    path('register/', views.register, name='register'),
    
    # Профили пользователей
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('profile/update/', views.ProfileUpdateView.as_view(), name='profile-update'),
    path('profile/deactivate/', views.ProfileDeactivateView.as_view(), name='profile-deactivate'),
    path('profile/<str:username>/', views.UserProfileView.as_view(), name='user-profile'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    
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
    path('users/', views.user_list, name='user-list'),
    path('user/<str:username>/', views.UserProfileView.as_view(), name='user-profile'),
    path('user/<str:username>/edit/', views.profile_edit, name='profile_edit'),
] 