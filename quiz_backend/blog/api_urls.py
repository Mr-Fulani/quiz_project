from django.urls import path
from .views import user_profile_stats_api, tinymce_image_upload, profile_api, social_links_api

app_name = 'blog_api'

urlpatterns = [
    path('profile/stats/', user_profile_stats_api, name='user_profile_stats_api'),
    path('profile/', profile_api, name='profile_api'),
    path('social-links/', social_links_api, name='social_links_api'),
] 