from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import api_views
from ..views import CategoryViewSet, PostViewSet, ProjectViewSet, check_auth

app_name = 'blog_api'

router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'posts', PostViewSet, basename='post')
router.register(r'projects', ProjectViewSet, basename='project')

urlpatterns = [
    path('check-auth/', check_auth, name='check_auth'),
    path('profile/stats/', api_views.user_profile_stats_api, name='user_profile_stats_api'),
    path('profile/', api_views.profile_api, name='profile_api'),
    path('social-links/', api_views.social_links_api, name='social_links_api'),
    path('resume/save/', api_views.save_resume_api, name='save_resume_api'),
    path('tinymce-upload/', api_views.tinymce_image_upload, name='tinymce_image_upload'),
    path('', include(router.urls)),
] 