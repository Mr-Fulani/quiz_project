from django.http import HttpResponse
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CategoryViewSet, PostViewSet, ProjectViewSet,
    HomePageView, PostDetailView, ProjectDetailView,
    ResumeView, PortfolioView, BlogView, AboutView,
    ContactView, QuizesView, QuizDetailView, inbox,
    send_message, delete_message, download_attachment,
    get_unread_messages_count, statistics_view, QuizSubtopicView, submit_task_answer, UniqueQuizTaskView,
    MaintenanceView, get_conversation
)
from django.shortcuts import redirect



app_name = 'blog'


def debug_view(request):
    return HttpResponse("Debug view is working!")

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

    path('debug/', debug_view, name='debug_view'),
    path('quizes/', QuizesView.as_view(), name='quizes'),
    path('quiz/<str:quiz_type>/', QuizDetailView.as_view(), name='quiz_detail'),
    # Сначала более специфичный маршрут с task_id
    path('quiz/<str:quiz_type>/<path:subtopic>/<int:task_id>/', UniqueQuizTaskView.as_view(), name='quiz_task_detail'),
    path('quiz/<str:quiz_type>/<path:subtopic>/<int:task_id>/submit/', submit_task_answer, name='submit_task_answer'),
    # Затем общий маршрут для subtopic
    path('quiz/<str:quiz_type>/<path:subtopic>/', QuizSubtopicView.as_view(), name='quiz_subtopic'),






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

    path('messages/conversation/<str:recipient_username>/', get_conversation, name='get_conversation'),
    #   -> Отображает переписку с конкретным пользователем

    path('statistics/', statistics_view, name='statistics'),
    #   -> Отображает общую статистику (blog/statistics.html)

    path('maintenance/', MaintenanceView.as_view(), name='maintenance'),
    #   -> Страница "В разработке"

    path('api/', include(router.urls)),
    #   -> Подключает URL-ы из DRF DefaultRouter:
    #      /api/categories/, /api/posts/, /api/projects/ и т.д.
]