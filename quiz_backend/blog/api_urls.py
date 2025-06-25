from django.urls import path
from .views import user_profile_stats_api

app_name = 'blog_api'

urlpatterns = [
    path('profile/stats/', user_profile_stats_api, name='user_profile_stats_api'),
] 