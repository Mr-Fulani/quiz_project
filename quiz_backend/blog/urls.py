from django.http import HttpResponse
from django.urls import path, include
from .views import (
    HomePageView, PostDetailView, ProjectDetailView,
    ResumeView, PortfolioView, BlogView, AboutView,
    ContactView, QuizesView, QuizDetailView, inbox,
    send_message, delete_message, download_attachment,
    get_unread_messages_count, statistics_view, submit_task_answer,
    MaintenanceView, get_conversation, add_testimonial, AllTestimonialsView, contact_form_submit, quiz_subtopic,
    quiz_difficulty, reset_subtopic_stats, check_auth
)
from django.shortcuts import redirect, render



app_name = 'blog'


def debug_view(request):
    return HttpResponse("Debug view is working!")


def telegram_auth_debug_view(request):
    """Диагностическая страница для отладки Telegram Login Widget"""
    return render(request, 'blog/telegram_auth_debug.html')


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
    path('telegram-auth-debug/', telegram_auth_debug_view, name='telegram_auth_debug'),
    path('quizes/', QuizesView.as_view(), name='quizes'),
    path('quiz/<str:quiz_type>/', QuizDetailView.as_view(), name='quiz_detail'),
    path('quiz/<str:quiz_type>/<slug:subtopic>/<int:task_id>/submit/', submit_task_answer, name='submit_task_answer'),
    path('stats/reset/subtopic/<int:subtopic_id>/', reset_subtopic_stats, name='reset_subtopic_stats'),
    path('quiz/<str:quiz_type>/<slug:subtopic>/', quiz_difficulty, name='quiz_difficulty'),
    path('quiz/<str:quiz_type>/<slug:subtopic>/<str:difficulty>/', quiz_subtopic, name='quiz_subtopic'),





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

    path('add-testimonial/', add_testimonial, name='add_testimonial'),
    path('testimonials/', AllTestimonialsView.as_view(), name='all_testimonials'),


    path('contact/submit/', contact_form_submit, name='contact_form_submit'),
    # Перенесено в blog/api/api_urls.py
    # path('api/check-auth/', check_auth, name='check_auth'),

]