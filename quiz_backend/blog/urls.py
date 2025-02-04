from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CategoryViewSet, PostViewSet, ProjectViewSet, 
    HomePageView, PostDetailView, ProjectDetailView, 
    ResumeView, PortfolioView, BlogView, AboutView, 
    ContactView, QuizesView, QuizDetailView, ProfileView, 
    profile_view, update_settings, inbox, 
    send_message, delete_message, download_attachment, 
    get_unread_messages_count, statistics_view
)
from django.shortcuts import redirect

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
    path('dashboard/', profile_view, name='profile'),  # Основная панель управления
    path('dashboard/update-settings/', update_settings, name='update_settings'),
    path('messages/', lambda request: redirect('blog:inbox'), name='messages'),
    path('inbox/', inbox, name='inbox'),
    path('messages/delete/<int:message_id>/', delete_message, name='delete_message'),
    path('messages/send/<str:recipient_username>/', send_message, name='send_message'),
    path('messages/attachment/<int:attachment_id>/', download_attachment, name='download_attachment'),
    path('messages/unread/count/', get_unread_messages_count, name='unread_messages_count'),
    path('statistics/', statistics_view, name='statistics'),
    path('api/', include(router.urls)),  # API endpoints
] 