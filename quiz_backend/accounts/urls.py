from django.urls import path
from django.contrib.auth import views as auth_views
from django.views.generic import RedirectView
from . import views
from .views import dashboard_view, profile_redirect_view, profile_view, update_settings

app_name = 'accounts'

urlpatterns = [
    # Регистрация нового пользователя
    path('register/', RedirectView.as_view(url='/?open_register=true'), name='register'),
    path('login/', RedirectView.as_view(url='/?open_login=true'), name='login'),

    # Аутентификация:  выход
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),

 
    # # Профили пользователей
    # path('profile/', views.ProfileView.as_view(), name='profile'),
    # #   -> Отображает профиль текущего пользователя (Generic APIView или TemplateView)
    # path('profile/update/', views.ProfileUpdateView.as_view(), name='profile-update'),
    #   -> Обновление профиля (PATCH/PUT)
    path('profile/deactivate/', views.ProfileDeactivateView.as_view(), name='profile-deactivate'),
    #   -> Деактивация профиля (изменение is_active и т.д.)
    path('profile/<str:username>/', views.UserProfileView.as_view(), name='user-profile'),
    #   -> Просмотр профиля пользователя по username (DetailView)
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    #   -> Функциональное представление для редактирования (форма)

    # Управление подписками
    path('subscriptions/', views.SubscriptionListView.as_view(), name='subscription-list'),
    #   -> Список подписок (ListCreateAPIView)
    path('subscriptions/<int:pk>/', views.SubscriptionDetailView.as_view(), name='subscription-detail'),
    #   -> Операции с конкретной подпиской (RetrieveUpdateDestroyAPIView)

    # Администраторы
    path('admins/', views.AdminListView.as_view(), name='admin-list'),
    #   -> Список всех администраторов (is_staff=True)
    path('admins/<int:admin_id>/', views.AdminDetailView.as_view(), name='admin-detail'),
    #   -> Управление конкретным администратором
    path('admins/telegram/', views.TelegramAdminListView.as_view(), name='telegram-admin-list'),
    #   -> Список Telegram-админов
    path('admins/django/', views.DjangoAdminListView.as_view(), name='django-admin-list'),
    #   -> Список Django-админов

    # Статистика
    path('stats/', views.UserStatsView.as_view(), name='user-stats'),
    #   -> Пример APIView, возвращающий простую статистику для пользователя

    # Список пользователей / профиль
    path('users/', views.user_list, name='user-list'),
    #   -> Функция, выводящая список пользователей (не staff), с пагинацией
    path('user/<str:username>/', views.UserProfileView.as_view(), name='user-profile'),
    #   -> DetailView профиля (аналогично profile/<str:username>/)
    path('user/<str:username>/edit/', views.profile_edit, name='profile_edit'),
    #   -> Редактирование профиля
    path('change-password/', views.change_password, name='change_password'),
    #   -> Смена пароля (функция change_password)

    path('dashboard/', dashboard_view, name='dashboard'),
    #   -> Личный кабинет пользователя (функция dashboard_view)

    path('profile/', profile_redirect_view, name='profile'),
    #   -> Редирект /profile/ -> /dashboard/

    path('profile/<str:username>/', profile_view, name='user_profile'),
    #   -> Просмотр профиля пользователя (profile_view)

    path('dashboard/update-settings/', update_settings, name='update_settings'),
    #   -> AJAX-вьюха для обновления настроек профиля

]