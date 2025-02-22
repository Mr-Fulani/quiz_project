import json
from datetime import datetime, timedelta

from accounts.models import CustomUser
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, F
from django.db.models.functions import TruncDate
from django.http import JsonResponse, FileResponse, Http404, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView, DetailView, ListView
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from tasks.models import Task, TaskTranslation, TaskStatistics
from topics.models import Topic, Subtopic

from .models import Category, Post, Project, Message, MessageAttachment
from .serializers import CategorySerializer, PostSerializer, ProjectSerializer

import logging

logger = logging.getLogger(__name__)


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


class HomePageView(TemplateView):
    """
    Отображает главную страницу сайта.

    Использует шаблон blog/index.html, предоставляет пагинированный список постов,
    категории и проекты.
    """
    template_name = 'blog/index.html'

    def get_context_data(self, **kwargs):
        """
        Добавляет данные в контекст шаблона.

        Включает пагинированный список постов (5 на страницу), категории (не портфолио),
        все проекты и категории портфолио.
        """
        context = super().get_context_data(**kwargs)
        posts_list = Post.objects.all()
        paginator = Paginator(posts_list, 5)
        page = self.request.GET.get('page')
        context['posts'] = paginator.get_page(page)
        context['categories'] = Category.objects.filter(is_portfolio=False)
        context['projects'] = Project.objects.all()
        context['portfolio_categories'] = Category.objects.filter(is_portfolio=True)
        return context


class AboutView(TemplateView):
    """
    Отображает страницу "Обо мне".

    Использует шаблон blog/about.html.
    """
    template_name = 'blog/about.html'

    def get_context_data(self, **kwargs):
        """
        Добавляет данные в контекст шаблона.

        Пока возвращает базовый контекст, можно расширить при необходимости.
        """
        context = super().get_context_data(**kwargs)
        return context


class PostDetailView(DetailView):
    """
    Отображает страницу отдельного поста.

    Использует модель Post и шаблон blog/post_detail.html.
    """
    model = Post
    template_name = 'blog/post_detail.html'
    context_object_name = 'post'

    def get_context_data(self, **kwargs):
        """
        Добавляет данные в контекст шаблона.

        Включает текущего пользователя, все категории и последние 5 постов.
        """
        context = super().get_context_data(**kwargs)
        context['user'] = self.request.user
        context['categories'] = Category.objects.all()
        context['posts'] = Post.objects.all()[:5]
        return context


class ProjectDetailView(DetailView):
    """
    Отображает страницу отдельного проекта.

    Использует модель Project и шаблон blog/project_detail.html.
    """
    model = Project
    template_name = 'blog/project_detail.html'
    context_object_name = 'project'

    def get_context_data(self, **kwargs):
        """
        Добавляет данные в контекст шаблона.

        Включает текущего пользователя, все категории и последние 5 проектов.
        """
        context = super().get_context_data(**kwargs)
        context['user'] = self.request.user
        context['categories'] = Category.objects.all()
        context['projects'] = Project.objects.all()[:5]
        return context


def blog_view(request):
    """
    Отображает страницу блога с фильтрацией по категории.

    Использует шаблон blog/blog.html, предоставляет пагинированный список постов (5 на страницу)
    и категории (не портфолио).
    """
    category_slug = request.GET.get('category')
    posts_list = Post.objects.all()

    if category_slug:
        posts_list = posts_list.filter(category__slug=category_slug)

    paginator = Paginator(posts_list, 5)
    page = request.GET.get('page')
    posts = paginator.get_page(page)

    categories = Category.objects.filter(is_portfolio=False)

    context = {
        'posts': posts,
        'categories': categories,
    }
    return render(request, 'blog/blog.html', context)


class ResumeView(TemplateView):
    """
    Отображает страницу резюме.

    Использует шаблон blog/resume.html.
    """
    template_name = 'blog/resume.html'

    def get_context_data(self, **kwargs):
        """
        Добавляет данные в контекст шаблона.

        Пока возвращает базовый контекст, можно расширить при необходимости.
        """
        context = super().get_context_data(**kwargs)
        return context


class PortfolioView(TemplateView):
    """
    Отображает страницу портфолио.

    Использует шаблон blog/portfolio.html, показывает проекты и категории портфолио.
    """
    template_name = 'blog/portfolio.html'

    def get_context_data(self, **kwargs):
        """
        Добавляет данные в контекст шаблона.

        Включает все проекты и категории с is_portfolio=True.
        """
        context = super().get_context_data(**kwargs)
        context['projects'] = Project.objects.all()
        context['portfolio_categories'] = Category.objects.filter(is_portfolio=True)
        return context


class BlogView(TemplateView):
    """
    Отображает страницу блога через TemplateView.

    Использует шаблон blog/blog_page.html, предоставляет пагинированный список постов
    и категории (не портфолио).
    """
    template_name = 'blog/blog_page.html'

    def get_context_data(self, **kwargs):
        """
        Добавляет данные в контекст шаблона.

        Включает пагинированный список постов (5 на страницу) и категории с is_portfolio=False.
        """
        context = super().get_context_data(**kwargs)
        posts_list = Post.objects.all()
        paginator = Paginator(posts_list, 5)
        page = self.request.GET.get('page')
        context['posts'] = paginator.get_page(page)
        context['categories'] = Category.objects.filter(is_portfolio=False)
        return context


class ContactView(TemplateView):
    """
    Отображает страницу "Контакты".

    Использует шаблон blog/contact.html.
    """
    template_name = 'blog/contact.html'


class QuizesView(ListView):
    """
    Отображает страницу списка тем для опросов.

    Использует шаблон blog/quizes.html, показывает только темы, у которых есть опубликованные
    задачи в таблице tasks.
    """
    template_name = 'blog/quizes.html'
    context_object_name = 'topics'

    def get_queryset(self):
        """
        Возвращает список тем с задачами.

        Фильтрует таблицу topics, оставляя только те темы, для которых есть хотя бы одна
        опубликованная задача в tasks.
        """
        return Topic.objects.filter(tasks__published=True).distinct()





class QuizDetailView(ListView):
    template_name = 'blog/quiz_detail.html'
    context_object_name = 'subtopics'

    def get_queryset(self):
        logger.info("QuizDetailView is running!")
        topic_name = self.kwargs['quiz_type'].lower()
        logger.info(f"Processing topic: {topic_name}")
        topic = get_object_or_404(Topic, name__iexact=topic_name)
        subtopics = Subtopic.objects.filter(topic=topic, tasks__published=True).distinct()
        logger.info(f"QuizDetailView - Topic: {topic_name}, Subtopics: {list(subtopics)}")
        return subtopics

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['topic'] = get_object_or_404(Topic, name__iexact=self.kwargs['quiz_type'].lower())
        logger.info(f"Context topic: {context['topic']}")
        return context

class QuizSubtopicView(ListView):
    template_name = 'blog/quiz_subtopic.html'
    context_object_name = 'tasks'
    paginate_by = 5

    def get_queryset(self):
        logger.info("QuizSubtopicView is running!")
        topic_name = self.kwargs['quiz_type'].lower()
        subtopic_name = self.kwargs['subtopic'].replace('%20', ' ')
        logger.info(f"Processing topic: {topic_name}, subtopic: {subtopic_name}")
        topic = get_object_or_404(Topic, name__iexact=topic_name)
        subtopic = get_object_or_404(Subtopic, topic=topic, name__iexact=subtopic_name)
        tasks = Task.objects.filter(topic=topic, subtopic=subtopic, published=True)
        logger.info(f"QuizSubtopicView - Topic: {topic_name}, Subtopic: {subtopic_name}, Tasks: {list(tasks)}")
        return tasks

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['topic'] = get_object_or_404(Topic, name__iexact=self.kwargs['quiz_type'].lower())
        context['subtopic'] = get_object_or_404(Subtopic, topic=context['topic'], name__iexact=self.kwargs['subtopic'].replace('%20', ' '))
        logger.info(f"Context topic: {context['topic']}, subtopic: {context['subtopic']}")
        for task in context['page_obj']:
            # Пробуем "ru", если нет — "en"
            task.translation = TaskTranslation.objects.filter(task=task, language="ru").first()
            if not task.translation:
                task.translation = TaskTranslation.objects.filter(task=task, language="en").first()
            logger.info(f"Task {task.id} translation: {task.translation}")
        return context





class UniqueQuizTaskView(DetailView):
    model = Task
    template_name = 'blog/quiz_task_detail.html'
    context_object_name = 'task'

    def get_object(self):
        task_id = self.kwargs.get('task_id')
        return Task.objects.get(id=task_id)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        task = self.get_object()
        quiz_type = self.kwargs.get('quiz_type')
        subtopic = self.kwargs.get('subtopic')
        print(f"UniqueQuizTaskView - Topic: {quiz_type}, Subtopic: {subtopic}, Task ID: {task.id}, Found: {task}")

        translation = TaskTranslation.objects.filter(task=task, language="en").first()
        context['translation'] = translation
        if translation:
            print(f"Task translation: {translation}")
            if isinstance(translation.answers, str):
                context['answers'] = json.loads(translation.answers)
            else:
                context['answers'] = translation.answers

        context['topic'] = {'name': quiz_type.capitalize()}
        context['subtopic'] = {'name': subtopic}
        context['submit_url'] = reverse('blog:submit_task_answer', kwargs={
            'quiz_type': quiz_type,
            'subtopic': subtopic,
            'task_id': task.id
        })

        is_correct_param = self.request.GET.get('is_correct')
        context['is_correct'] = True if is_correct_param == 'True' else False if is_correct_param == 'False' else None
        context['selected_answer'] = self.request.GET.get('selected')
        context['error'] = self.request.GET.get('error')  # Добавляем параметр ошибки
        print(
            f"is_correct: {context['is_correct']}, selected_answer: {context['selected_answer']}, error: {context['error']}")
        return context







@login_required
@csrf_exempt
def submit_task_answer(request, quiz_type, subtopic, task_id):
    if request.method == 'POST':
        topic = get_object_or_404(Topic, name__iexact=quiz_type)
        subtopic_obj = get_object_or_404(Subtopic, topic=topic, name__iexact=subtopic)
        task = get_object_or_404(Task, id=task_id, topic=topic, subtopic=subtopic_obj, published=True)

        translation = TaskTranslation.objects.filter(task=task, language="en").first()
        if not translation:
            return JsonResponse({'error': 'Translation not found'}, status=400)

        selected_answer = request.POST.get('answer')
        if not selected_answer:
            # Редирект с параметром ошибки
            return HttpResponseRedirect(
                reverse('blog:quiz_task_detail',
                        kwargs={'quiz_type': quiz_type, 'subtopic': subtopic, 'task_id': task_id}) +
                '?error=no_answer'
            )

        if isinstance(translation.answers, str):
            answers = json.loads(translation.answers)
        else:
            answers = translation.answers

        is_correct = selected_answer == translation.correct_answer
        total_votes = task.statistics.count() + 1

        results = []
        for answer in answers:
            votes = task.statistics.filter(successful=(answer == translation.correct_answer)).count()
            if answer == selected_answer and not is_correct:
                votes += 1
            percentage = (votes / total_votes * 100) if total_votes > 0 else 0
            results.append({
                'text': answer,
                'votes': votes,
                'is_correct': answer == translation.correct_answer,
                'percentage': percentage
            })

        stats, created = TaskStatistics.objects.get_or_create(
            user=request.user,
            task=task,
            defaults={'attempts': 1, 'successful': is_correct}
        )
        if not created:
            stats.attempts = F('attempts') + 1
            stats.successful = is_correct
            stats.save(update_fields=['attempts', 'successful'])

        return HttpResponseRedirect(
            reverse('blog:quiz_task_detail',
                    kwargs={'quiz_type': quiz_type, 'subtopic': subtopic, 'task_id': task_id}) +
            f'?is_correct={is_correct}&selected={selected_answer}'
        )
    return JsonResponse({'error': 'Invalid request method'}, status=405)






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
def send_message(request, recipient_username):
    """
    Отправляет новое сообщение пользователю.

    Принимает содержимое из POST['content'] и вложения из request.FILES['attachments'],
    создаёт запись в Message и MessageAttachment. Требует авторизации.
    """
    recipient = get_object_or_404(CustomUser, username=recipient_username)
    content = request.POST.get('content')

    if content:
        message = Message.objects.create(
            sender=request.user,
            recipient=recipient,
            content=content
        )

        files = request.FILES.getlist('attachments')
        for file in files:
            MessageAttachment.objects.create(
                message=message,
                file=file,
                filename=file.name
            )

        return JsonResponse({
            'status': 'sent',
            'message_id': message.id,
            'created_at': message.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })

    return JsonResponse({'status': 'error', 'message': 'Требуется содержимое'}, status=400)


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
    Отображает страницу входящих и исходящих сообщений.

    Использует шаблон accounts/inbox.html, помечает все непрочитанные сообщения как прочитанные.
    Требует авторизации.
    """
    Message.objects.filter(
        recipient=request.user,
        is_read=False,
        is_deleted_by_recipient=False
    ).update(is_read=True)

    incoming_messages = Message.objects.filter(
        recipient=request.user,
        is_deleted_by_recipient=False
    ).select_related('sender').prefetch_related('attachments')

    outgoing_messages = Message.objects.filter(
        sender=request.user,
        is_deleted_by_sender=False
    ).select_related('recipient').prefetch_related('attachments')

    return render(request, 'accounts/inbox.html', {
        'incoming_messages': incoming_messages,
        'outgoing_messages': outgoing_messages
    })


@login_required
def get_unread_messages_count(request):
    """
    Возвращает количество непрочитанных сообщений текущего пользователя.

    Формат ответа — JSON с полем 'count'. Требует авторизации.
    """
    count = Message.objects.filter(recipient=request.user, is_read=False).count()
    return JsonResponse({'count': count})


def index(request):
    """
    Отображает главную страницу с пользователями.

    Использует шаблон blog/index.html, показывает всех пользователей (кроме staff).
    """
    User = get_user_model()
    context = {
        'users': User.objects.exclude(is_staff=True).select_related('profile').order_by('-date_joined')
    }
    return render(request, 'blog/index.html', context)


def custom_404(request, exception=None):
    """
    Обрабатывает ошибку 404.

    Перенаправляет на страницу '404'.
    """
    return redirect('404')


def statistics_view(request):
    """
    Отображает страницу статистики по квизам и пользователям.

    Использует шаблон accounts/statistics.html, предоставляет общую статистику и,
    если пользователь авторизован и указан параметр view=personal, личную статистику.
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    context = {
        'total_users': CustomUser.objects.count(),
        'total_quizzes_completed': TaskStatistics.objects.count(),
        'avg_score': (TaskStatistics.objects.filter(successful=True).count() * 100.0 /
                      TaskStatistics.objects.count()) if TaskStatistics.objects.exists() else 0,
        'activity_dates': json.dumps([
            (start_date + timedelta(n)).strftime('%d.%m')
            for n in range(31)
        ]),
        'activity_data': json.dumps(
            list(
                TaskStatistics.objects.filter(last_attempt_date__gte=start_date)
                .annotate(date=TruncDate('last_attempt_date'))
                .values('date')
                .annotate(count=Count('id'))
                .values_list('count', flat=True)
            )
        ),
        'categories_labels': json.dumps(
            list(
                Topic.objects.annotate(task_count=Count('tasks'))
                .values_list('name', flat=True)
            )
        ),
        'categories_data': json.dumps(
            list(
                Topic.objects.annotate(task_count=Count('tasks'))
                .values_list('task_count', flat=True)
            )
        ),
        'scores_distribution': json.dumps([
            TaskStatistics.objects.filter(attempts__gt=0, attempts__lte=i + 5).count()
            for i in range(0, 25, 5)
        ])
    }

    if request.user.is_authenticated and request.GET.get('view') == "personal":
        try:
            stats = request.user.statistics.first()
        except AttributeError:
            stats = None

        if stats:
            context['user_stats'] = {
                'successful_attempts': 1 if stats.successful else 0,
                'total_attempts': stats.attempts,
                'success_rate': 100.0 if stats.successful else 0.0,
            }
        else:
            context['user_stats'] = {
                'successful_attempts': 0,
                'total_attempts': 0,
                'success_rate': 0.0,
            }

    return render(request, 'accounts/statistics.html', context)