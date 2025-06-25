# blog/views.py
import io
import json
import logging
import os
import random
import uuid
from datetime import datetime, timedelta

from PIL import Image
from accounts.models import CustomUser
from accounts.models import DjangoAdmin
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db import transaction, connection
from django.db.models import Count, F, Q, Max, Prefetch
import logging

logger = logging.getLogger(__name__)
from django.db.models.functions import TruncDate
from django.http import JsonResponse, FileResponse, Http404
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _, get_language
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods
from django.views.generic import TemplateView, DetailView, ListView
from rest_framework import viewsets, filters, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response as DRFResponse
from rest_framework.decorators import action
from rest_framework.response import Response
from tasks.models import Task, TaskTranslation, TaskStatistics
from topics.models import Topic, Subtopic


from .mixins import BreadcrumbsMixin
from .models import Category, Post, Project, Message, MessageAttachment, PageVideo, Testimonial, MarqueeText
from .serializers import CategorySerializer, PostSerializer, ProjectSerializer

logger = logging.getLogger(__name__)




def check_auth(request):
    """
    Проверяет, авторизован ли пользователь.

    Returns:
        JsonResponse: JSON с полем is_authenticated (true/false).
    """
    return JsonResponse({'is_authenticated': request.user.is_authenticated})



class CategoryViewSet(viewsets.ModelViewSet):
    """
    ViewSet для модели Category.

    Обеспечивает стандартные операции REST API: получение списка, создание,
    просмотр одной записи, обновление и удаление категорий. Поиск выполняется по полю slug.
    """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    lookup_field = 'slug'


class PostViewSet(viewsets.ModelViewSet):
    """
    ViewSet для модели Post.

    Предоставляет CRUD-операции, поиск по заголовку и содержимому, сортировку по дате
    создания и количеству просмотров. Добавляет метод для увеличения счётчика просмотров.
    """
    queryset = Post.objects.all()
    serializer_class = PostSerializer
    lookup_field = 'slug'
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'content']
    ordering_fields = ['created_at', 'views_count']

    def get_queryset(self):
        """
        Возвращает отфильтрованный набор постов.

        Если запрос — получение списка (list), возвращаются только опубликованные посты.
        Для других операций возвращаются все посты.
        """
        if self.action == 'list':
            return Post.objects.filter(published=True)
        return Post.objects.all()

    @action(detail=True, methods=['post'])
    def increment_views(self, request, slug=None):
        """
        Увеличивает счётчик просмотров поста.

        Метод доступен по POST-запросу на /posts/<slug>/increment_views/.
        Возвращает обновлённое количество просмотров в JSON.
        """
        post = self.get_object()
        post.views_count += 1
        post.save()
        return Response({'views_count': post.views_count})

    def perform_create(self, serializer):
        """
        Устанавливает дату публикации при создании поста.

        Если пост создаётся с флагом published=True, автоматически устанавливается текущая дата
        в поле published_at.
        """
        if serializer.validated_data.get('published', False):
            serializer.validated_data['published_at'] = timezone.now()
        serializer.save()


class ProjectViewSet(viewsets.ModelViewSet):
    """
    ViewSet для модели Project.

    Обеспечивает CRUD-операции, поиск по заголовку, описанию и технологиям,
    сортировку по дате создания. Есть метод для получения избранных проектов.
    """
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    lookup_field = 'slug'
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description', 'technologies']
    ordering_fields = ['created_at']

    @action(detail=False, methods=['get'])
    def featured(self, request):
        """
        Возвращает список избранных проектов.

        Доступен по GET-запросу на /projects/featured/. Возвращает проекты с флагом featured=True
        в формате JSON.
        """
        featured_projects = Project.objects.filter(featured=True)
        serializer = self.get_serializer(featured_projects, many=True)
        return Response(serializer.data)


class HomePageView(BreadcrumbsMixin, TemplateView):
    """
    Отображает главную страницу сайта.
    Использует шаблон blog/index.html, предоставляет пагинированный список постов,
    категории, проекты, видео.
    """
    template_name = 'blog/index.html'
    breadcrumbs = [{'name': _('Главная'), 'url': reverse_lazy('blog:home')}]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        posts_list = Post.objects.filter(published=True)
        paginator = Paginator(posts_list, 5)
        page = self.request.GET.get('page')
        context['posts'] = paginator.get_page(page)
        context['categories'] = Category.objects.filter(is_portfolio=False)
        context['projects'] = Project.objects.all()
        context['portfolio_categories'] = Category.objects.filter(is_portfolio=True)
        context['posts_with_video'] = Post.objects.filter(
            Q(published=True) & (Q(video_url__isnull=False, video_url__gt='') | Q(images__video__isnull=False))
        ).distinct()
        context['page_videos'] = PageVideo.objects.filter(page='index')
        context['marquee_texts'] = MarqueeText.objects.filter(is_active=True).order_by('order')
        context['meta_title'] = _('Quiz Python, Go, JavaScript, Java, C#')
        return context


class AboutView(BreadcrumbsMixin, TemplateView):
    """
    Отображает страницу "Обо мне".
    Использует шаблон blog/about.html, предоставляет видео, отзывы.
    """
    template_name = 'blog/about.html'
    breadcrumbs = [
        {'name': _('Главная'), 'url': reverse_lazy('blog:home')},
        {'name': _('Обо мне'), 'url': reverse_lazy('blog:about')},
    ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['posts_with_video'] = Post.objects.filter(
            Q(published=True) & (Q(video_url__isnull=False, video_url__gt='') | Q(images__video__isnull=False))
        ).distinct()
        context['page_videos'] = PageVideo.objects.filter(page='about')
        context['testimonials'] = Testimonial.objects.filter(is_approved=True)
        return context

    @method_decorator(login_required)
    @method_decorator(require_http_methods(["POST"]))
    def post(self, request, *args, **kwargs):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            text = request.POST.get('text')
            if text:
                Testimonial.objects.create(
                    user=request.user,
                    text=text
                )
                return JsonResponse({'success': True})
        return JsonResponse({'success': False})



class PostDetailView(BreadcrumbsMixin, DetailView):
    """
    Обработчик отображения страницы отдельного поста.
    Использует шаблон blog/post_detail.html, предоставляет данные поста,
    связанные посты, видео и SEO-данные.
    """
    model = Post
    template_name = 'blog/post_detail.html'
    context_object_name = 'post'

    def get_breadcrumbs(self):
        """
        Возвращает динамические крошки для поста.
        """
        post = self.object
        return [
            {'name': _('Главная'), 'url': reverse_lazy('blog:home')},
            {'name': _('Блог'), 'url': reverse_lazy('blog:blog')},
            {'name': post.title, 'url': reverse_lazy('blog:post_detail', kwargs={'slug': post.slug})},
        ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        post = self.object
        related_posts = Post.objects.filter(
            published=True,
            category=post.category
        ).exclude(id=post.id)[:3]
        context['meta_title'] = post.title
        context['meta_description'] = post.meta_description or post.excerpt[:160] or post.content[:160]
        context['meta_keywords'] = post.meta_keywords or (post.category.name if post.category else post.title)
        context['og_title'] = post.title
        context['og_description'] = context['meta_description']
        first_image = post.images.first()
        context['og_image'] = (
            first_image.photo.url
            if first_image and first_image.photo
            else '/static/blog/images/default-og-image.jpg'
        )
        context['og_url'] = self.request.build_absolute_uri()
        context['canonical_url'] = context['og_url']
        context['hreflang_url'] = context['og_url']
        context['related_posts'] = related_posts
        context['page_videos'] = PageVideo.objects.filter(page='post_detail')
        return context







class ProjectDetailView(BreadcrumbsMixin, DetailView):
    """
    Обработчик отображения страницы отдельного проекта.
    Использует шаблон blog/project_detail.html, предоставляет данные проекта,
    связанные проекты, видео и SEO-данные.
    """
    model = Project
    template_name = 'blog/project_detail.html'
    context_object_name = 'project'

    def get_breadcrumbs(self):
        """
        Возвращает динамические крошки для проекта.
        """
        project = self.object
        return [
            {'name': _('Главная'), 'url': reverse_lazy('blog:home')},
            {'name': _('Портфолио'), 'url': reverse_lazy('blog:portfolio')},
            {'name': project.title, 'url': reverse_lazy('blog:project_detail', kwargs={'slug': project.slug})},
        ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project = self.object
        related_projects = Project.objects.filter(
            featured=True,
            category=project.category
        ).exclude(id=project.id)[:3]
        context['meta_title'] = project.title
        context['meta_description'] = project.description[:160] if project.description else project.title[:160]
        context['meta_keywords'] = project.meta_keywords if project.meta_keywords else project.title
        context['og_title'] = project.title
        context['og_description'] = context['meta_description']
        context['og_image'] = (
            project.images.first().photo.url
            if project.images.exists() and project.images.first().photo
            else '/static/blog/images/default-og-image.jpg'
        )
        context['og_url'] = self.request.build_absolute_uri()
        context['canonical_url'] = context['og_url']
        context['hreflang_url'] = context['og_url']
        context['related_projects'] = related_projects
        context['page_videos'] = PageVideo.objects.filter(page='project_detail')
        return context






class ResumeView(BreadcrumbsMixin, TemplateView):
    """
    Отображает страницу "Резюме".
    Использует шаблон blog/resume.html, предоставляет информацию об админских правах.
    """
    template_name = 'blog/resume.html'
    breadcrumbs = [
        {'name': _('Главная'), 'url': reverse_lazy('blog:home')},
        {'name': _('Резюме'), 'url': reverse_lazy('blog:resume')},
    ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_admin'] = self.request.user.is_staff if self.request.user.is_authenticated else False
        context['meta_description'] = _('My professional resume with experience and skills.')
        context['meta_keywords'] = _('resume, programmer, portfolio')
        return context



class PortfolioView(BreadcrumbsMixin, TemplateView):
    """
    Отображает страницу портфолио.
    Использует шаблон blog/portfolio.html, показывает проекты и категории портфолио.
    """
    template_name = 'blog/portfolio.html'
    breadcrumbs = [
        {'name': _('Главная'), 'url': reverse_lazy('blog:home')},
        {'name': _('Портфолио'), 'url': reverse_lazy('blog:portfolio')},
    ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['projects'] = Project.objects.all()
        context['portfolio_categories'] = Category.objects.filter(is_portfolio=True)
        context['meta_description'] = _('Explore my portfolio of projects.')  # Добавлено
        context['meta_keywords'] = _('portfolio, projects, programming')
        return context




class BlogView(BreadcrumbsMixin, TemplateView):
    """
    Отображает страницу блога.
    Использует шаблон blog/blog_page.html, предоставляет пагинированный список постов и категории.
    """
    template_name = 'blog/blog_page.html'
    breadcrumbs = [
        {'name': _('Главная'), 'url': reverse_lazy('blog:home')},
        {'name': _('Блог'), 'url': reverse_lazy('blog:blog')},
    ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        posts_list = Post.objects.all()
        paginator = Paginator(posts_list, 5)
        page = self.request.GET.get('page')
        context['posts'] = paginator.get_page(page)
        context['categories'] = Category.objects.all()
        context['meta_description'] = _('Explore articles and posts on programming and quizzes.')
        context['meta_keywords'] = _('blog, programming, quizzes')
        return context


class ContactView(BreadcrumbsMixin, TemplateView):
    """
    Отображает страницу "Контакты".
    Использует шаблон blog/contact.html, предоставляет форму обратной связи.
    """
    template_name = 'blog/contact.html'
    breadcrumbs = [
        {'name': _('Главная'), 'url': reverse_lazy('blog:home')},
        {'name': _('Контакты'), 'url': reverse_lazy('blog:contact')},
    ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['meta_description'] = _('Get in touch with us.')  # Добавлено
        context['meta_keywords'] = _('contact, feedback, quiz project')
        return context







@require_POST
def contact_form_submit(request):
    """
    Обрабатывает отправку формы обратной связи.

    Создаёт сообщение от системного пользователя 'Anonymous' вместо sender=None.
    """
    logger.info("Получен POST-запрос на /contact/submit/")
    fullname = request.POST.get('fullname')
    email = request.POST.get('email')
    message_text = request.POST.get('message')

    if not all([fullname, email, message_text]):
        logger.warning("Не все поля формы заполнены")
        return JsonResponse({'status': 'error', 'message': 'Все поля обязательны'}, status=400)

    try:
        # Находим администратора
        admin_email = settings.EMAIL_ADMIN[0] if settings.EMAIL_ADMIN else None
        admin_user = None
        if admin_email:
            admin_user = CustomUser.objects.filter(email=admin_email).first()
            if not admin_user:
                logger.warning(f"Администратор с email {admin_email} не найден")

        # Находим или создаём системного пользователя для анонимных сообщений
        anonymous_user, _ = CustomUser.objects.get_or_create(
            username='Anonymous',
            defaults={
                'email': 'anonymous@quizproject.com',
                'is_active': True,
                'is_staff': False
            }
        )

        # Отправляем письмо
        subject = f'Новое сообщение от {fullname} ({email})'
        message = f'Имя: {fullname}\nEmail: {email}\nСообщение:\n{message_text}'
        from_email = settings.DEFAULT_FROM_EMAIL
        recipient_list = settings.EMAIL_ADMIN

        logger.info(f"Отправка письма на {recipient_list}")
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=recipient_list,
            fail_silently=False,
        )

        # Сохраняем сообщение в базе
        message_obj = Message.objects.create(
            sender=anonymous_user,  # Используем системного пользователя
            recipient=admin_user,
            content=message_text,
            fullname=fullname,
            email=email,
            is_read=False
        )
        logger.info(f"Сообщение сохранено в базе от {email} для {admin_user or 'No recipient'}")

        logger.info(f"Сообщение успешно отправлено от {email}")
        return JsonResponse({'status': 'success', 'message': 'Сообщение отправлено'})
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения: {str(e)}")
        return JsonResponse({'status': 'error', 'message': f'Ошибка отправки: {str(e)}'}, status=500)




class QuizesView(BreadcrumbsMixin, ListView):
    """
    Отображает страницу списка тем для опросов.
    Использует шаблон blog/quizes.html, показывает только темы с опубликованными задачами.
    """
    template_name = 'blog/quizes.html'
    context_object_name = 'topics'
    breadcrumbs = [
        {'name': _('Главная'), 'url': reverse_lazy('blog:home')},
        {'name': _('Квизы'), 'url': reverse_lazy('blog:quizes')},
    ]

    def get_queryset(self):
        return Topic.objects.filter(tasks__published=True).distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['meta_description'] = _('Test your knowledge with our interactive quizzes.')  # Добавлено
        context['meta_keywords'] = _('quizzes, tests, programming')  # Добавлено
        return context







class QuizDetailView(BreadcrumbsMixin, ListView):
    """
    Отображает список подтем для выбранной темы.

    Фильтрует подтемы по теме и наличию опубликованных задач с переводом на текущий язык.

    Attributes:
        template_name (str): Шаблон ('blog/quiz_detail.html').
        context_object_name (str): Имя объекта в контексте ('subtopics').
    """
    template_name = 'blog/quiz_detail.html'
    context_object_name = 'subtopics'

    def get_queryset(self):
        """
        Возвращает подтемы с задачами на текущем языке.

        Использует select_related и prefetch_related для минимизации запросов.

        Returns:
            Queryset: Список подтем.
        """
        topic_name = self.kwargs['quiz_type'].lower()
        topic = get_object_or_404(Topic, name__iexact=topic_name)
        preferred_language = get_language()
        subtopics = Subtopic.objects.filter(
            topic=topic,
            tasks__published=True,
            tasks__translations__language=preferred_language
        ).select_related('topic').prefetch_related(
            Prefetch(
                'tasks',
                queryset=Task.objects.filter(
                    published=True,
                    translations__language=preferred_language
                ).select_related('topic', 'subtopic').prefetch_related(
                    Prefetch(
                        'translations',
                        queryset=TaskTranslation.objects.filter(language=preferred_language)
                    )
                )
            )
        ).distinct()
        logger.info(f"QuizDetailView - Topic: {topic_name}, Subtopics: {subtopics.count()}, Language: {preferred_language}")
        logger.info(f"Total queries: {len(connection.queries)}")
        return subtopics

    def get_breadcrumbs(self):
        """
        Возвращает хлебные крошки.

        Returns:
            list: Список словарей с названиями и URL.
        """
        topic = get_object_or_404(Topic, name__iexact=self.kwargs['quiz_type'].lower())
        return [
            {'name': _('Главная'), 'url': reverse_lazy('blog:home')},
            {'name': _('Квизы'), 'url': reverse_lazy('blog:quizes')},
            {'name': topic.name, 'url': reverse_lazy('blog:quiz_detail', kwargs={'quiz_type': topic.name.lower()})},
        ]

    def get_context_data(self, **kwargs):
        """
        Формирует контекст для шаблона.

        Returns:
            dict: Контекст с темой и метаданными.
        """
        context = super().get_context_data(**kwargs)
        context['topic'] = get_object_or_404(Topic, name__iexact=self.kwargs['quiz_type'].lower())
        context['meta_title'] = _('%(topic_name)s Quizzes') % {'topic_name': context['topic'].name}
        context['meta_description'] = _('Explore quizzes on %(topic_name)s.') % {'topic_name': context['topic'].name}
        context['meta_keywords'] = _('%(topic_name)s, quizzes, programming') % {'topic_name': context['topic'].name}
        if not context['subtopics']:
            context['no_subtopics_message'] = _(
                'No subtopics with tasks available in your language for %(topic_name)s.'
            ) % {'topic_name': context['topic'].name}
        return context





def quiz_difficulty(request, quiz_type, subtopic):
    """
    Отображает уровни сложности для подтемы, фильтруя по наличию задач с переводом на текущий язык сайта.

    Функция запрашивает подтему по указанным теме и имени подтемы, затем определяет доступные уровни сложности,
    основываясь на задачах с переводом на текущий язык сайта (определяемый через get_language()). Используется
    для рендеринга шаблона blog/quiz_difficulty.html.

    Args:
        request: HTTP-запрос.
        quiz_type (str): Название темы (например, 'python').
        subtopic (str): Подтема (например, 'api-requests').

    Returns:
        HttpResponse: Рендеринг шаблона blog/quiz_difficulty.html с контекстом.

    Raises:
        Http404: Если тема или подтема не найдены.
    """
    logger.info(f"quiz_difficulty: {quiz_type}/{subtopic}")
    topic = get_object_or_404(Topic, name__iexact=quiz_type)
    normalized_subtopic = subtopic.replace('-', '[ -/]')
    subtopic_query = Q(topic=topic, name__iregex=normalized_subtopic)
    logger.info(f"Searching subtopic: original={subtopic}, regex={normalized_subtopic}")
    try:
        subtopic_obj = Subtopic.objects.get(subtopic_query)
    except Subtopic.DoesNotExist:
        logger.error(f"Subtopic not found for query: {subtopic_query}")
        raise Http404(f"Subtopic {subtopic} not found for topic {quiz_type}")

    preferred_language = get_language()  # Изменено: используем get_language()

    # Определяем доступные уровни сложности
    difficulty_names = {
        'easy': str(_('Easy')),
        'medium': str(_('Medium')),
        'hard': str(_('Hard')),
    }
    difficulties = []
    for diff in ['easy', 'medium', 'hard']:
        if Task.objects.filter(
            topic=topic,
            subtopic=subtopic_obj,
            published=True,
            difficulty=diff,
            translations__language=preferred_language  # Изменено: добавлена фильтрация по языку
        ).exists() or Task.objects.filter(
            topic=topic,
            subtopic__isnull=True,
            published=True,
            difficulty=diff,
            translations__language=preferred_language  # Изменено: добавлена фильтрация по языку
        ).exists():
            difficulties.append({'value': diff, 'name': difficulty_names[diff]})  # Изменено: локализованное имя

    logger.info(f"Found {len(difficulties)} difficulties for subtopic '{subtopic_obj.name}' on language '{preferred_language}'")  # Изменено: добавлено логирование

    context = {
        'topic': topic,
        'subtopic': subtopic_obj,
        'difficulties': difficulties,
        'breadcrumbs': [
            {'name': str(_('Home')), 'url': reverse_lazy('blog:home')},
            {'name': str(_('Quizzes')), 'url': reverse_lazy('blog:quizes')},
            {'name': topic.name, 'url': reverse_lazy('blog:quiz_detail', kwargs={'quiz_type': topic.name.lower()})},
            {'name': subtopic_obj.name, 'url': reverse_lazy('blog:quiz_difficulty', kwargs={'quiz_type': topic.name.lower(), 'subtopic': subtopic})},
        ],
        'breadcrumbs_json_ld': {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": index + 1,
                    "name": crumb['name'],
                    "item": request.build_absolute_uri(crumb['url'])
                }
                for index, crumb in enumerate([
                    {'name': str(_('Home')), 'url': reverse_lazy('blog:home')},
                    {'name': str(_('Quizzes')), 'url': reverse_lazy('blog:quizes')},
                    {'name': topic.name, 'url': reverse_lazy('blog:quiz_detail', kwargs={'quiz_type': topic.name.lower()})},
                    {'name': subtopic_obj.name, 'url': reverse_lazy('blog:quiz_difficulty', kwargs={'quiz_type': topic.name.lower(), 'subtopic': subtopic})},
                ])
            ]
        },
        'meta_title': _('%(subtopic_name)s Difficulty Levels — Quiz Project') % {'subtopic_name': subtopic_obj.name},  # Изменено: приведено к стилю quiz_subtopic
        'meta_description': _('Choose difficulty levels for %(subtopic_name)s quizzes.') % {'subtopic_name': subtopic_obj.name},  # Изменено: приведено к стилю quiz_subtopic
        'meta_keywords': _('%(subtopic_name)s, difficulty levels, quizzes, programming') % {'subtopic_name': subtopic_obj.name},  # Изменено: приведено к стилю quiz_subtopic
    }

    return render(request, 'blog/quiz_difficulty.html', context)







def quiz_subtopic(request, quiz_type, subtopic, difficulty):
    """
    Отображает задачи для подтемы и уровня сложности с пагинацией.

    Запрашивает задачи с переводом на текущий язык и статистикой для авторизованного пользователя.
    Использует select_related и prefetch_related для оптимизации запросов. Обрабатывает варианты
    ответов, добавляя опцию "I don't know" и перемешивая их.

    Args:
        request: HTTP-запрос.
        quiz_type (str): Название темы (например, 'golang').
        subtopic (str): Подтема (например, 'interfaces').
        difficulty (str): Уровень сложности ('easy', 'medium', 'hard').

    Returns:
        HttpResponse: Рендеринг шаблона 'blog/quiz_subtopic.html'.
    """
    logger.info(f"Starting quiz_subtopic: {quiz_type}/{subtopic}/{difficulty}")
    topic = get_object_or_404(Topic, name__iexact=quiz_type)
    normalized_subtopic = subtopic.replace('-', '[ -/]')
    subtopic_obj = get_object_or_404(Subtopic, topic=topic, name__iregex=normalized_subtopic)
    preferred_language = get_language()

    # Оптимизированный запрос задач
    tasks = (
        Task.objects.filter(
            topic=topic,
            subtopic=subtopic_obj,
            published=True,
            difficulty=difficulty.lower(),
            translations__language=preferred_language
        )
        .select_related('topic', 'subtopic')
        .prefetch_related(
            Prefetch(
                'translations',
                queryset=TaskTranslation.objects.filter(language=preferred_language)
            ),
            Prefetch(
                'statistics',
                queryset=TaskStatistics.objects.filter(
                    user=request.user
                ).select_related('user') if request.user.is_authenticated else TaskStatistics.objects.none()
            )
        )
    )

    if not tasks.exists():
        tasks = (
            Task.objects.filter(
                topic=topic,
                subtopic__isnull=True,
                published=True,
                difficulty=difficulty.lower(),
                translations__language=preferred_language
            )
            .select_related('topic')
            .prefetch_related(
                Prefetch(
                    'translations',
                    queryset=TaskTranslation.objects.filter(language=preferred_language)
                ),
                Prefetch(
                    'statistics',
                    queryset=TaskStatistics.objects.filter(
                        user=request.user
                    ).select_related('user') if request.user.is_authenticated else TaskStatistics.objects.none()
                )
            )
        )

    # Пагинация
    page_number = request.GET.get('page', 1)
    paginator = Paginator(tasks, 3)
    page_obj = paginator.get_page(page_number)

    # Словарь для опции "I don't know"
    dont_know_option_dict = {
        'ru': str(_('I don\'t know, but I want to learn')),
        'en': str(_('I don\'t know, but I want to learn')),
    }

    # Обработка переводов и ответов
    for task in page_obj:
        translation = task.translations.first()  # Перевод уже загружен через prefetch_related
        task.translation = translation
        if translation:
            try:
                answers = translation.answers if isinstance(translation.answers, list) else json.loads(translation.answers)
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing answers for task {task.id}: {e}")
                answers = []
            options = answers[:]
            random.shuffle(options)
            dont_know_option = dont_know_option_dict.get(translation.language, dont_know_option_dict['ru'])
            options.append(dont_know_option)
            task.answers = options
            task.correct_answer = translation.correct_answer
        else:
            task.answers = []
            task.correct_answer = None
            logger.warning(f"No translation found for task {task.id} on language {preferred_language}")

    # Формируем словарь статистики
    if request.user.is_authenticated:
        task_stats = TaskStatistics.objects.filter(
            user=request.user,
            task__id__in=[task.id for task in page_obj]
        ).values('task_id', 'selected_answer')
        task_stats_dict = {stat['task_id']: stat['selected_answer'] for stat in task_stats}
        for task in page_obj:
            task.is_solved = task.id in task_stats_dict
            task.selected_answer = task_stats_dict.get(task.id)

    difficulty_names = {
        'easy': str(_('Easy')),
        'medium': str(_('Medium')),
        'hard': str(_('Hard')),
    }
    context = {
        'topic': topic,
        'subtopic': subtopic_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'difficulty': difficulty,
        'breadcrumbs': [
            {'name': str(_('Home')), 'url': reverse_lazy('blog:home')},
            {'name': str(_('Quizzes')), 'url': reverse_lazy('blog:quizes')},
            {'name': topic.name, 'url': reverse_lazy('blog:quiz_detail', kwargs={'quiz_type': topic.name.lower()})},
            {'name': subtopic_obj.name, 'url': reverse_lazy('blog:quiz_difficulty', kwargs={'quiz_type': topic.name.lower(), 'subtopic': subtopic})},
            {'name': difficulty_names.get(difficulty.lower(), difficulty.title()), 'url': reverse_lazy('blog:quiz_subtopic', kwargs={'quiz_type': topic.name.lower(), 'subtopic': subtopic, 'difficulty': difficulty})},
        ],
        'meta_title': _('%(subtopic_name)s — %(difficulty)s Quizzes') % {'subtopic_name': subtopic_obj.name, 'difficulty': difficulty.title()},
        'meta_description': _('Test your skills with %(subtopic_name)s quizzes on %(difficulty)s level.') % {'subtopic_name': subtopic_obj.name, 'difficulty': difficulty.title()},
        'meta_keywords': _('%(subtopic_name)s, quizzes, %(difficulty)s, programming') % {'subtopic_name': subtopic_obj.name, 'difficulty': difficulty.title()},
    }

    logger.info(f"Total queries in quiz_subtopic: {len(connection.queries)}")
    return render(request, 'blog/quiz_subtopic.html', context)




@login_required
def submit_task_answer(request, quiz_type, subtopic, task_id):
    """
    Обрабатывает ответ на задачу через AJAX.

    Args:
        request: HTTP-запрос.
        quiz_type: Название темы (например, 'python').
        subtopic: Подтема (например, 'api-requests-with-json').
        task_id: ID задачи.

    Returns:
        JsonResponse: Результат обработки ответа.
    """
    if request.method != 'POST':
        logger.error(f"Invalid request method for task_id={task_id}, method={request.method}")
        return JsonResponse({'error': 'Invalid request method'}, status=400)

    topic = get_object_or_404(Topic, name__iexact=quiz_type)
    cleaned_subtopic = subtopic.replace('-', ' ').replace('/', ' ')
    subtopic_obj = get_object_or_404(Subtopic, topic=topic, name__iexact=cleaned_subtopic)
    task = get_object_or_404(Task, id=task_id, topic=topic, subtopic=subtopic_obj, published=True)

    preferred_language = request.user.language if request.user.is_authenticated else 'ru'
    translation = (TaskTranslation.objects.filter(task=task, language=preferred_language).first() or
                   TaskTranslation.objects.filter(task=task).first())

    if not translation:
        logger.error(f"No translation found for task_id={task_id}, topic={quiz_type}, subtopic={subtopic}")
        stats, created = TaskStatistics.objects.get_or_create(
            user=request.user,
            task=task,
            defaults={
                'attempts': 1,
                'successful': False,
                'selected_answer': request.POST.get('answer', 'No translation')
            }
        )
        if not created:
            stats.attempts = F('attempts') + 1
            stats.save(update_fields=['attempts'])
        return JsonResponse({'error': 'No translation available'}, status=400)

    selected_answer = request.POST.get('answer')
    if not selected_answer:
        logger.error(f"No answer provided for task_id={task_id}")
        return JsonResponse({'error': 'No answer provided'}, status=400)

    if isinstance(translation.answers, str):
        try:
            answers = json.loads(translation.answers)
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing answers JSON for task_id={task_id}: {e}")
            return JsonResponse({'error': 'Invalid answer format'}, status=400)
    else:
        answers = translation.answers

    dont_know_options = [
        "Я не знаю, но хочу узнать",
        "I don't know, but I want to learn",
    ]
    if selected_answer not in answers and selected_answer not in dont_know_options:
        logger.error(f"Invalid answer selected for task_id={task_id}: {selected_answer}")
        return JsonResponse({'error': 'Invalid answer selected'}, status=400)

    is_correct = selected_answer == translation.correct_answer
    total_votes = task.statistics.count() + 1
    results = []
    for answer in answers:
        votes = task.statistics.filter(selected_answer=answer).count()
        if answer == selected_answer:
            votes += 1
        percentage = (votes / total_votes * 100) if total_votes > 0 else 0
        results.append({
            'text': answer,
            'is_correct': answer == translation.correct_answer,
            'percentage': percentage
        })

    stats, created = TaskStatistics.objects.get_or_create(
        user=request.user,
        task=task,
        defaults={
            'attempts': 1,
            'successful': is_correct,
            'selected_answer': selected_answer
        }
    )
    if not created:
        stats.attempts = F('attempts') + 1
        stats.successful = is_correct
        stats.selected_answer = selected_answer
        stats.save(update_fields=['attempts', 'successful', 'selected_answer'])

    logger.info(f"Answer submitted for task_id={task_id}, user={request.user}, is_correct={is_correct}")
    return JsonResponse({
        'status': 'success',
        'is_correct': is_correct,
        'selected_answer': selected_answer,
        'results': results,
        'explanation': translation.explanation if translation else 'No explanation available.'
    })


@login_required
def reset_subtopic_stats(request, subtopic_id):
    """
    Сбрасывает статистику пользователя для всех задач в подтеме.

    Args:
        request: HTTP-запрос.
        subtopic_id: ID подтемы.

    Returns:
        JsonResponse: Статус операции.
    """
    if request.method != 'POST':
        logger.error(
            f"Invalid request method for reset_subtopic_stats, subtopic_id={subtopic_id}, method={request.method}")
        return JsonResponse({'error': 'Invalid request method'}, status=400)

    subtopic = get_object_or_404(Subtopic, id=subtopic_id)
    logger.info(f"Resetting stats for user={request.user}, subtopic={subtopic.name} (id={subtopic_id})")

    try:
        deleted_count = TaskStatistics.objects.filter(
            user=request.user,
            task__subtopic=subtopic
        ).delete()[0]
        logger.info(f"Deleted {deleted_count} stats records for user={request.user}, subtopic={subtopic.name}")

        return JsonResponse({
            'status': 'success',
            'message': f'Статистика для подтемы "{subtopic.name}" сброшена.',
            'deleted_count': deleted_count
        })
    except Exception as e:
        logger.error(f"Error resetting stats for subtopic_id={subtopic_id}, user={request.user}: {str(e)}")
        return JsonResponse({'error': 'Failed to reset statistics'}, status=500)






@login_required
@require_POST
def delete_message(request, message_id):
    """
    Удаляет сообщение мягким способом.

    Если сообщение удалено обоими пользователями (отправителем и получателем),
    оно удаляется полностью вместе с вложениями. Требует авторизации.
    """
    message = get_object_or_404(Message, id=message_id)
    if request.user not in [message.recipient, message.sender]:
        return JsonResponse({'status': 'error', 'message': 'Доступ запрещён'}, status=403)

    message.soft_delete(request.user)

    if message.is_completely_deleted:
        for attachment in message.attachments.all():
            if attachment.file:
                attachment.file.delete()
            attachment.delete()
        message.delete()

    return JsonResponse({'status': 'success'})





@login_required
@require_POST
def send_message(request):
    """
    Отправляет новое сообщение пользователю.

    Принимает содержимое из POST['content'], вложения из request.FILES['attachments'],
    и recipient_username из POST['recipient_username']. Ограничивает размер вложений до 20 МБ.
    Разрешает отправку с пустым текстом, если есть вложения.
    Проверяет типы файлов (jpg, jpeg, png, gif, pdf, mp4) и ограничивает количество вложений до 5.
    Требует авторизации.

    Returns:
        JsonResponse: Статус отправки сообщения и детали (message_id, created_at) или ошибка.
    """
    logger.info(f"send_message: Запрос от {request.user.username}")
    recipient_username = request.POST.get('recipient_username')
    if not recipient_username:
        logger.error("send_message: Получатель не указан")
        return JsonResponse({'status': 'error', 'message': 'Получатель не указан'}, status=400)

    recipient = get_object_or_404(CustomUser, username=recipient_username)
    content = request.POST.get('content', '').strip()
    files = request.FILES.getlist('attachments')

    # Проверка: нужен либо текст, либо вложения
    if not content and not files:
        logger.error("send_message: Требуется текст или вложения")
        return JsonResponse({'status': 'error', 'message': 'Требуется текст или вложения'}, status=400)

    # Ограничение на количество вложений (максимум 5)
    max_attachments = 5
    if len(files) > max_attachments:
        logger.error(f"send_message: Превышено максимальное количество вложений ({len(files)} > {max_attachments})")
        return JsonResponse({
            'status': 'error',
            'message': f'Максимальное количество вложений: {max_attachments}'
        }, status=400)

    # Проверка размера и типа вложений
    max_file_size = 20 * 1024 * 1024  # 20 MB
    allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.pdf', '.mp4']
    for file in files:
        # Проверка размера
        if file.size > max_file_size:
            logger.error(f"send_message: Файл '{file.name}' превышает лимит в 20 МБ")
            return JsonResponse({
                'status': 'error',
                'message': f'Файл "{file.name}" превышает лимит в 20 МБ'
            }, status=400)
        # Проверка расширения
        ext = os.path.splitext(file.name)[1].lower()
        if ext not in allowed_extensions:
            logger.error(f"send_message: Недопустимый тип файла '{file.name}' (разрешены: {', '.join(allowed_extensions)})")
            return JsonResponse({
                'status': 'error',
                'message': f'Недопустимый тип файла "{file.name}". Разрешены: {", ".join(allowed_extensions)}'
            }, status=400)

    try:
        with transaction.atomic():
            # Проверка на дублирование сообщения (в течение 5 секунд)
            recent_messages = Message.objects.filter(
                sender=request.user,
                recipient=recipient,
                content=content,
                created_at__gte=timezone.now() - timezone.timedelta(seconds=5)
            )
            if recent_messages.exists() and not files:
                existing_message = recent_messages.first()
                logger.warning(
                    f"send_message: Обнаружено дублирование сообщения от {request.user.username} к {recipient.username}"
                )
                return JsonResponse({
                    'status': 'sent',
                    'message_id': existing_message.id,
                    'created_at': existing_message.created_at.strftime('%Y-%m-%d %H:%M:%S')
                })

            # Создаём сообщение
            message = Message.objects.create(
                sender=request.user,
                recipient=recipient,
                content=content
            )
            logger.info(f"send_message: Создано сообщение {message.id} от {request.user.username} к {recipient.username}")

            # Добавляем вложения
            for file in files:
                attachment = MessageAttachment.objects.create(
                    message=message,
                    file=file,
                    filename=file.name
                )
                logger.info(f"send_message: Добавлено вложение {attachment.id} к сообщению {message.id}")

            return JsonResponse({
                'status': 'sent',
                'message_id': message.id,
                'created_at': message.created_at.strftime('%Y-%m-%d %H:%M:%S')
            })

    except Exception as e:
        logger.error(f"send_message: Ошибка при создании сообщения: {str(e)}")
        return JsonResponse({'status': 'error', 'message': 'Ошибка сервера'}, status=500)






@login_required
def get_conversation(request, recipient_username):
    """
    Возвращает сообщения между текущим пользователем и указанным recipient_username.
    Отмечает непрочитанные сообщения как прочитанные.
    """
    logger.info(f"get_conversation: Запрос от {request.user.username} для {recipient_username}")
    recipient = get_object_or_404(CustomUser, username=recipient_username)
    user = request.user

    # Отмечаем непрочитанные сообщения как прочитанные
    Message.objects.filter(
        recipient=user,
        sender=recipient,
        is_read=False,
        is_deleted_by_recipient=False
    ).update(is_read=True)

    # Получаем сообщения (входящие и исходящие) в хронологическом порядке
    messages = Message.objects.filter(
        (
            Q(sender=user, recipient=recipient, is_deleted_by_sender=False) |
            Q(sender=recipient, recipient=user, is_deleted_by_recipient=False)
        )
    ).select_related('sender', 'recipient').prefetch_related('attachments').order_by('created_at')

    # Формируем JSON-ответ
    messages_data = []
    for message in messages:
        attachments = [
            {
                'id': att.id,
                'filename': att.filename,
                'url': att.file.url,
                'is_image': att.filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))
            }
            for att in message.attachments.all()
        ]
        messages_data.append({
            'id': message.id,
            'content': message.content,
            'sender_username': message.sender.username,
            'created_at': message.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'is_sent_by_user': message.sender == user,
            'attachments': attachments
        })

    logger.info(f"get_conversation: Возвращено {len(messages_data)} сообщений")
    return JsonResponse({'messages': messages_data})




@login_required
def download_attachment(request, attachment_id):
    """
    Скачивает вложение из сообщения.

    Проверяет, что пользователь — отправитель или получатель сообщения, и возвращает файл.
    Требует авторизации.
    """
    attachment = get_object_or_404(MessageAttachment, id=attachment_id)
    message = attachment.message

    if request.user not in [message.sender, message.recipient]:
        raise PermissionDenied

    response = FileResponse(attachment.file)
    response['Content-Disposition'] = f'attachment; filename="{attachment.filename}"'
    return response


@login_required
def inbox(request):
    """
    Отображает страницу чата с диалогами.

    Показывает список диалогов текущего пользователя, исключая сообщения от анонимных отправителей
    и диалоги с удалёнными или деактивированными пользователями. Подсчитывает только непрочитанные
    сообщения от активных пользователей, исключая удалённые сообщения.

    Args:
        request: HTTP-запрос.

    Returns:
        HttpResponse: Рендеринг шаблона accounts/inbox.html с контекстом диалогов.
    """
    user = request.user
    logger.info(f"Fetching inbox for user: {user.username}")

    # Получаем уникальных собеседников, исключая сообщения с sender=None и удалённые сообщения
    dialogs = Message.objects.filter(
        (Q(sender=user, is_deleted_by_sender=False) | Q(recipient=user, is_deleted_by_recipient=False)) &
        Q(sender__isnull=False)  # Исключаем анонимные сообщения
    ).values('sender', 'recipient').annotate(
        last_message_id=Max('id')
    ).distinct().order_by('-last_message_id')

    dialog_list = []
    seen_users = set()  # Для исключения дубликатов
    for dialog in dialogs:
        other_user_id = dialog['recipient'] if dialog['sender'] == user.id else dialog['sender']
        if other_user_id in seen_users:
            continue
        seen_users.add(other_user_id)

        try:
            # Проверяем, существует ли пользователь и активен ли он
            other_user = CustomUser.objects.get(id=other_user_id, is_active=True)
        except CustomUser.DoesNotExist:
            logger.warning(f"User with id={other_user_id} does not exist or is inactive, skipping dialog")
            continue

        try:
            last_message = Message.objects.get(id=dialog['last_message_id'])
            # Подсчет непрочитанных сообщений с учетом всех условий
            unread_count = Message.objects.filter(
                recipient=user,
                sender=other_user,
                is_read=False,
                is_deleted_by_recipient=False,
                sender__is_active=True,  # Учитываем только активных отправителей
                sender__isnull=False  # Исключаем анонимные сообщения
            ).count()
            if unread_count > 0:
                logger.debug(f"Found {unread_count} unread messages for dialog with user {other_user.username}")
            dialog_list.append({
                'user': other_user,
                'last_message': last_message,
                'unread_count': unread_count
            })
        except Message.DoesNotExist:
            logger.warning(f"Last message with id={dialog['last_message_id']} not found, skipping dialog")
            continue

    logger.info(f"Found {len(dialog_list)} valid dialogs for user: {user.username}")
    return render(request, 'accounts/inbox.html', {
        'dialogs': dialog_list
    })



@login_required
def get_unread_messages_count(request):
    """
    Возвращает количество непрочитанных сообщений текущего пользователя.

    Формат ответа — JSON с полем 'count'. Требует авторизации.
    """
    count = Message.objects.filter(recipient=request.user, is_read=False).count()
    return JsonResponse({'count': count})
















def custom_404(request, exception=None):
    """
    Обрабатывает ошибку 404.

    Перенаправляет на страницу '404'.
    """
    return redirect('404')






@login_required
def statistics_view(request):
    """
    Отображает статистику по квизам.

    Показывает общую или личную статистику (view=personal).

    Args:
        request: HTTP-запрос.

    Returns:
        HttpResponse: Рендеринг 'accounts/statistics.html'.
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    # Общая статистика
    stats = TaskStatistics.objects.aggregate(
        total_quizzes=Count('id'),
        successful_quizzes=Count('id', filter=Q(successful=True))
    )
    total_users = CustomUser.objects.count()
    total_quizzes_completed = stats['total_quizzes']
    avg_score = (
        (stats['successful_quizzes'] / total_quizzes_completed * 100.0)
        if total_quizzes_completed else 0
    )

    # Графики: активность
    activity_stats = TaskStatistics.objects.filter(
        last_attempt_date__date__gte=start_date,
        last_attempt_date__date__lte=end_date
    ).values('last_attempt_date__date').annotate(count=Count('id')).order_by('last_attempt_date__date')
    activity_dates = [(start_date + timedelta(n)).strftime('%d.%m') for n in range(31)]
    activity_data = [0] * 31
    for stat in activity_stats:
        day_index = (stat['last_attempt_date__date'] - start_date.date()).days
        if 0 <= day_index < 31:
            activity_data[day_index] = stat['count']

    # Графики: категории
    categories_stats = Topic.objects.annotate(task_count=Count('tasks')).values('name', 'task_count')
    categories_labels = [stat['name'] for stat in categories_stats] or ['No data']
    categories_data = [stat['task_count'] for stat in categories_stats] or [0]

    # Графики: попытки
    scores_distribution = [
        TaskStatistics.objects.filter(attempts__gt=i, attempts__lte=i + 5).count()
        for i in range(0, 25, 5)
    ]

    context = {
        'total_users': total_users,
        'total_quizzes_completed': total_quizzes_completed,
        'avg_score': avg_score,
        'activity_dates': json.dumps(activity_dates),
        'activity_data': json.dumps(activity_data),
        'categories_labels': json.dumps(categories_labels),
        'categories_data': json.dumps(categories_data),
        'scores_distribution': json.dumps(scores_distribution),
    }

    # Личная статистика
    if request.user.is_authenticated:
        user_stats = TaskStatistics.objects.filter(user=request.user).aggregate(
            total_attempts=Count('id'),
            successful_attempts=Count('id', filter=Q(successful=True)),
            rating=Count('id')
        )
        user_stats['success_rate'] = (
            round((user_stats['successful_attempts'] / user_stats['total_attempts']) * 100, 1)
            if user_stats['total_attempts'] > 0 else 0
        )
        user_stats['solved_tasks'] = user_stats['successful_attempts']

        # Личная активность
        user_activity_stats = TaskStatistics.objects.filter(
            user=request.user,
            last_attempt_date__isnull=False
        ).values('last_attempt_date__date').annotate(count=Count('id')).order_by('last_attempt_date__date')
        user_activity_dates = [stat['last_attempt_date__date'].strftime('%d.%m') for stat in user_activity_stats] or ['No data']
        user_activity_data = [stat['count'] for stat in user_activity_stats] or [0]

        # Личные категории
        user_category_stats = TaskStatistics.objects.filter(user=request.user).values(
            'task__topic__name'
        ).annotate(count=Count('id')).order_by('-count')[:5]
        user_categories_labels = [stat['task__topic__name'] or 'Unknown' for stat in user_category_stats] or ['No data']
        user_categories_data = [stat['count'] for stat in user_category_stats] or [0]

        # Личные попытки
        user_attempts = TaskStatistics.objects.filter(user=request.user).values('attempts').annotate(count=Count('id'))
        user_attempts_distribution = [0] * 5
        for attempt in user_attempts:
            attempts_value = int(attempt['attempts'] or 0)
            bin_index = min((attempts_value - 1) // 5, 4) if attempts_value > 0 else 0
            user_attempts_distribution[bin_index] += attempt['count']

        context.update({
            'user_stats': user_stats,
            'sidebar_stats': user_stats,
            'unread_messages_count': request.user.received_messages.filter(is_read=False).count(),
            'activity_dates': json.dumps(user_activity_dates if request.GET.get('view') == 'personal' else activity_dates),
            'activity_data': json.dumps(user_activity_data if request.GET.get('view') == 'personal' else activity_data),
            'categories_labels': json.dumps(user_categories_labels if request.GET.get('view') == 'personal' else categories_labels),
            'categories_data': json.dumps(user_categories_data if request.GET.get('view') == 'personal' else categories_data),
            'scores_distribution': json.dumps(user_attempts_distribution if request.GET.get('view') == 'personal' else scores_distribution),
        })

    return render(request, 'accounts/statistics.html', context)




class MaintenanceView(BreadcrumbsMixin, TemplateView):
    """
    Отображает страницу технического обслуживания.
    Использует шаблон blog/maintenance.html.
    """
    template_name = 'blog/maintenance.html'
    breadcrumbs = [
        {'name': _('Главная'), 'url': reverse_lazy('blog:home')},
        {'name': _('Техническое обслуживание'), 'url': reverse_lazy('blog:maintenance')},
    ]




@login_required
def add_testimonial(request):
    if request.method == 'POST' and request.is_ajax():
        text = request.POST.get('text')
        if text:
            testimonial = Testimonial.objects.create(
                user=request.user,
                text=text
            )
            return JsonResponse({'success': True})
    return JsonResponse({'success': False})




class AllTestimonialsView(BreadcrumbsMixin, ListView):
    """
    Отображает страницу со всеми одобренными отзывами.
    Использует шаблон blog/all_testimonials.html, показывает 4 отзыва на страницу.
    """
    template_name = 'blog/all_testimonials.html'
    model = Testimonial
    context_object_name = 'testimonials'
    paginate_by = 4
    breadcrumbs = [
        {'name': _('Главная'), 'url': reverse_lazy('blog:home')},
        {'name': _('Отзывы'), 'url': reverse_lazy('blog:all_testimonials')},
    ]

    def get_queryset(self):
        return Testimonial.objects.filter(is_approved=True).order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Все отзывы')
        return context

    @method_decorator(login_required)
    def post(self, request, *args, **kwargs):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            text = request.POST.get('text')
            if text:
                Testimonial.objects.create(
                    user=request.user,
                    text=text
                )
                return JsonResponse({'success': True})
        return JsonResponse({'success': False})




@csrf_exempt
def tinymce_image_upload(request):
    """Обработчик загрузки изображений для TinyMCE с сжатием."""
    if request.method == 'POST' and request.FILES.get('file'):
        image = request.FILES['file']
        max_size = 5 * 1024 * 1024  # 5 MB
        if image.size > max_size:
            return JsonResponse({'error': 'Файл слишком большой (максимум 5 МБ)'}, status=400)

        # Генерируем уникальное имя файла
        ext = image.name.split('.')[-1].lower()
        if ext not in ['jpg', 'jpeg', 'png']:
            return JsonResponse({'error': 'Недопустимый формат изображения'}, status=400)
        filename = f"{uuid.uuid4()}.jpg"  # Сохраняем как JPEG
        upload_path = os.path.join('tinymce_uploads', filename)
        full_path = os.path.join(settings.MEDIA_ROOT, upload_path)

        # Сжимаем изображение
        img = Image.open(image)
        img = img.convert('RGB')  # Конвертируем в RGB для JPEG
        if img.width > 800 or img.height > 800:
            img.thumbnail((800, 800), Image.LANCZOS)  # Изменяем размер
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=85, optimize=True)
        output.seek(0)

        # Сохраняем файл
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'wb+') as destination:
            destination.write(output.read())

        # Возвращаем URL изображения
        image_url = f"{settings.MEDIA_URL}{upload_path}"
        return JsonResponse({'location': image_url})

    return JsonResponse({'error': 'Неверный запрос'}, status=400)


# API для мини-приложения: статистика профиля пользователя
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def user_profile_stats_api(request):
    """
    API endpoint для получения статистики профиля пользователя для мини-приложения
    """
    try:
        user = request.user
        
        # Основная статистика пользователя (используем ту же логику что и в statistics_view)
        user_stats = TaskStatistics.objects.filter(user=user).aggregate(
            total_attempts=Count('id'),
            successful_attempts=Count('id', filter=Q(successful=True)),
            rating=Count('id')
        )
        
        success_rate = (
            round((user_stats['successful_attempts'] / user_stats['total_attempts']) * 100, 1)
            if user_stats['total_attempts'] > 0 else 0
        )
        
        # Прогресс по темам (топ 5)
        topic_progress = []
        user_category_stats = TaskStatistics.objects.filter(user=user).values(
            'task__topic__name',
            'task__topic__id'
        ).annotate(
            completed=Count('id', filter=Q(successful=True)),
            total=Count('id')
        ).order_by('-total')[:5]
        
        for stat in user_category_stats:
            topic_name = stat['task__topic__name'] or 'Unknown'
            completed = stat['completed']
            total = stat['total']
            percentage = round((completed / total * 100), 0) if total > 0 else 0
            
            topic_progress.append({
                'name': topic_name,
                'completed': completed,
                'total': total,
                'percentage': percentage
            })
        
        # Подсчет очков (пример: 10 очков за правильный ответ)
        total_points = user_stats['successful_attempts'] * 10
        
        # Серия (streak) - считаем последние попытки подряд
        recent_attempts = TaskStatistics.objects.filter(
            user=user
        ).order_by('-last_attempt_date')[:10]
        
        current_streak = 0
        best_streak = 0
        temp_streak = 0
        
        for attempt in recent_attempts:
            if attempt.successful:
                temp_streak += 1
                if current_streak == 0:  # Это первая успешная попытка в серии
                    current_streak = temp_streak
            else:
                if temp_streak > best_streak:
                    best_streak = temp_streak
                temp_streak = 0
        
        if temp_streak > best_streak:
            best_streak = temp_streak
            
        # Информация о пользователе
        user_info = {
            'telegram_id': getattr(user, 'telegram_id', None) or user.id,
            'username': user.username,
            'first_name': user.first_name or user.username,
            'last_name': user.last_name or '',
            'avatar_url': None  # Пока без аватаров
        }
        
        # Моковые достижения (позже можно сделать реальную систему)
        achievements = [
            {'id': 1, 'name': 'Первый шаг', 'icon': '🏆', 'unlocked': user_stats['total_attempts'] > 0},
            {'id': 2, 'name': 'Знаток Python', 'icon': '🐍', 'unlocked': success_rate > 60},
            {'id': 3, 'name': 'Веб-мастер', 'icon': '🌐', 'unlocked': False},
            {'id': 4, 'name': 'Серия', 'icon': '🔥', 'unlocked': current_streak >= 3},
            {'id': 5, 'name': 'Эксперт', 'icon': '⭐', 'unlocked': success_rate > 90},
            {'id': 6, 'name': 'Скорость', 'icon': '⚡', 'unlocked': False}
        ]
        
        return DRFResponse({
            'user': user_info,
            'stats': {
                'total_quizzes': user_stats['total_attempts'],
                'completed_quizzes': user_stats['successful_attempts'],
                'success_rate': int(success_rate),
                'total_points': total_points,
                'current_streak': current_streak,
                'best_streak': best_streak
            },
            'topic_progress': topic_progress,
            'achievements': achievements
        })
        
    except Exception as e:
        logger.error(f"Ошибка в user_profile_stats_api: {e}")
        return DRFResponse({
            'error': 'Не удалось загрузить статистику профиля'
        }, status=500)