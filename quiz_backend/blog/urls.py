from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CategoryViewSet, PostViewSet, ProjectViewSet,
    HomePageView, PostDetailView, ProjectDetailView,
    ResumeView, PortfolioView, BlogView, AboutView,
    ContactView, QuizesView, QuizDetailView, inbox,
    send_message, delete_message, download_attachment,
    get_unread_messages_count, statistics_view
)
from django.shortcuts import redirect

app_name = 'blog'

# Создаём DefaultRouter для DRF ViewSet-ов (Category, Post, Project).
router = DefaultRouter()
router.register(r'categories', CategoryViewSet)
router.register(r'posts', PostViewSet)
router.register(r'projects', ProjectViewSet)

urlpatterns = [
    path('', HomePageView.as_view(), name='home'),
    #   -> Главная страница, класс HomePageView (TemplateView).

    path('post/<slug:slug>/', PostDetailView.as_view(), name='post_detail'),
    #   -> Отображение одного поста (DetailView)

    path('project/<slug:slug>/', ProjectDetailView.as_view(), name='project_detail'),
    #   -> Отображение одного проекта (DetailView)

    path('resume/', ResumeView.as_view(), name='resume'),
    #   -> Страница резюме

    path('portfolio/', PortfolioView.as_view(), name='portfolio'),
    #   -> Страница портфолио

    path('blog/', BlogView.as_view(), name='blog'),
    #   -> Страница блога (TemplateView)

    path('about/', AboutView.as_view(), name='about'),
    #   -> Страница "Обо мне"

    path('contact/', ContactView.as_view(), name='contact'),
    #   -> Страница "Контакты"

    path('quizes/', QuizesView.as_view(), name='quizes'),
    #   -> Страница со списком викторин

    path('quiz/<str:quiz_type>/', QuizDetailView.as_view(), name='quiz_detail'),
    #   -> Детальная информация о квизе (по quiz_type)

    # path('dashboard/', dashboard_view, name='dashboard'),
    # #   -> Личный кабинет пользователя (функция dashboard_view)
    #
    # path('profile/', profile_redirect_view, name='profile'),
    # #   -> Редирект /profile/ -> /dashboard/
    #
    # path('profile/<str:username>/', profile_view, name='user_profile'),
    # #   -> Просмотр профиля пользователя (profile_view)
    #
    # path('dashboard/update-settings/', update_settings, name='update_settings'),
    # #   -> AJAX-вьюха для обновления настроек профиля

    path('messages/', lambda request: redirect('blog:inbox'), name='messages'),
    #   -> Редирект /messages/ -> /inbox/

    path('inbox/', inbox, name='inbox'),
    #   -> Показ входящих / исходящих сообщений

    path('messages/delete/<int:message_id>/', delete_message, name='delete_message'),
    #   -> "Мягкое" удаление сообщения

    path('messages/send/', send_message, name='send_message'),
    #   -> Отправка нового сообщения (POST)

    path('messages/attachment/<int:attachment_id>/', download_attachment, name='download_attachment'),
    #   -> Скачивание вложения из сообщения

    path('messages/unread/count/', get_unread_messages_count, name='unread_messages_count'),
    #   -> Возвращает JSON с количеством непрочитанных сообщений

    path('statistics/', statistics_view, name='statistics'),
    #   -> Отображает общую статистику (blog/statistics.html)

    path('api/', include(router.urls)),
    #   -> Подключает URL-ы из DRF DefaultRouter:
    #      /api/categories/, /api/posts/, /api/projects/ и т.д.
]