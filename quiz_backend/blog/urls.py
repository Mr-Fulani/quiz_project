from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, PostViewSet, ProjectViewSet, HomePageView, PostDetailView, ProjectDetailView, ResumeView, PortfolioView, BlogView, AboutView, ContactView, QuizesView, QuizDetailView, ProfileView

app_name = 'blog'

router = DefaultRouter()
router.register(r'categories', CategoryViewSet)
router.register(r'posts', PostViewSet)
router.register(r'projects', ProjectViewSet)

urlpatterns = [
    path('', HomePageView.as_view(), name='home'),  # Главная страница
    path('post/<slug:slug>/', PostDetailView.as_view(), name='post_detail'),
    path('project/<slug:slug>/', ProjectDetailView.as_view(), name='project_detail'),
    path('resume/', ResumeView.as_view(), name='resume'),  # Новый URL
    path('portfolio/', PortfolioView.as_view(), name='portfolio'),
    path('blog/', BlogView.as_view(), name='blog'),
    path('about/', AboutView.as_view(), name='about'),
    path('contact/', ContactView.as_view(), name='contact'),  # Добавляем URL для contact
    path('quizes/', QuizesView.as_view(), name='quizes'),
    path('quiz/<str:quiz_type>/', QuizDetailView.as_view(), name='quiz_detail'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('api/', include(router.urls)),  # API endpoints
] 