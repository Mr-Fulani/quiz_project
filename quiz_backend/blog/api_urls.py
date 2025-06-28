from django.urls import path
from .api import views as api_views

app_name = 'blog_api'

urlpatterns = [
    path('profile/stats/', api_views.user_profile_stats_api, name='user_profile_stats_api'),
    path('profile/', api_views.profile_api, name='profile_api'),
    path('social-links/', api_views.social_links_api, name='social_links_api'),
    path('tinymce-upload/', api_views.tinymce_image_upload, name='tinymce_image_upload'),
] 