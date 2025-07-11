from django.urls import path
from django.views.generic import RedirectView
from . import views
from .api import api_views
from .views import (
    dashboard_view, profile_redirect_view, profile_view, update_settings,
    update_personal_info, custom_password_reset_view,
    CustomPasswordResetConfirmView, CustomPasswordResetDoneView,
    CustomPasswordResetCompleteView
)

app_name = 'accounts'

urlpatterns = [
    # Auth URLs that are hit by forms. They must point to the correct handlers.
    path('register/', api_views.RegisterView.as_view(), name='register'),
    path('login/', RedirectView.as_view(url='/?open_login=true'), name='login'), # This is for redirecting, not submitting.
    path('login-ajax/', api_views.LoginView.as_view(), name='login_ajax'), # This is for the AJAX form submission.

    # Logout (template-based)
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),

    # Профили пользователей (template-based views)
    path('user/<str:username>/', views.UserProfileView.as_view(), name='user_profile'),
    path('profile/<str:username>/', profile_view, name='full_profile'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('profile/', profile_redirect_view, name='profile'),

    # Список пользователей
    path('users/', views.user_list, name='user-list'),

    # Настройки и обновления (AJAX handlers для template views)
    path('settings/update/', update_settings, name='update_settings'),
    path('dashboard/change-password/', views.change_password, name='change_password'),
    path('dashboard/update-personal-info/', update_personal_info, name='update_personal_info'),

    # Кастомные password reset URLs
    path('password_reset/', custom_password_reset_view, name='password_reset'),
    path('password_reset/done/', CustomPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', CustomPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('password-reset-complete/', CustomPasswordResetCompleteView.as_view(), name='password_reset_complete'),
]