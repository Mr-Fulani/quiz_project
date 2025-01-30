from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, PostViewSet, ProjectViewSet, HomePageView, PostDetailView, ProjectDetailView

app_name = 'blog'

router = DefaultRouter()
router.register(r'categories', CategoryViewSet)
router.register(r'posts', PostViewSet)
router.register(r'projects', ProjectViewSet)

urlpatterns = [
    path('', HomePageView.as_view(), name='home'),  # Главная страница
    path('post/<slug:slug>/', PostDetailView.as_view(), name='post_detail'),
    path('project/<slug:slug>/', ProjectDetailView.as_view(), name='project_detail'),
    path('api/', include(router.urls)),  # API endpoints
] 