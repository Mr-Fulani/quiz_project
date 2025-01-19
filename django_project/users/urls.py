from django.urls import path
from . import views



app_name = 'users'



urlpatterns = [
    path('profile/<int:telegram_id>/', views.user_profile, name='user_profile'),
    path('section/<str:section_name>/', views.load_section, name='load_section'),
    path('profile/<int:telegram_id>/update/', views.update_profile, name='update_profile'),
]
