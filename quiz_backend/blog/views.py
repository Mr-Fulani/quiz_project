import json
import random
from datetime import datetime, timedelta

from accounts.models import CustomUser
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, F, Q, Max
from django.db.models.functions import TruncDate
from django.http import JsonResponse, FileResponse, Http404, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods
from django.views.generic import TemplateView, DetailView, ListView
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from tasks.models import Task, TaskTranslation, TaskStatistics
from topics.models import Topic, Subtopic

from .models import Category, Post, Project, Message, MessageAttachment, PageVideo, Testimonial
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
    категории, проекты и данные из personal_info.
    """
    template_name = 'blog/index.html'

    def get_context_data(self, **kwargs):
        """
        Добавляет данные в контекст шаблона, не трогая personal_info из процессора.
        """
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

        # Отладка: проверяем наличие personal_info и его содержимое
        logger.info("=== DEBUG: Context keys: %s", list(context.keys()))
        logger.info("=== DEBUG: personal_info: %s", context.get('personal_info', 'Not set'))
        if 'personal_info' in context:
            logger.info("=== DEBUG: personal_info.resources: %s", context['personal_info'].get('resources', 'Not set'))
            logger.info("=== DEBUG: personal_info.top_users: %s", context['personal_info'].get('top_users', 'Not set'))

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
        """
        context = super().get_context_data(**kwargs)
        # Добавляем посты с видео
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
    template_name = 'blog/resume.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_admin'] = self.request.user.is_staff if self.request.user.is_authenticated else False
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
    paginate_by = 3  # 3 задачи на страницу

    def get_queryset(self):
        topic_name = self.kwargs['quiz_type']
        subtopic_name = self.kwargs['subtopic']
        topic = get_object_or_404(Topic, name__iexact=topic_name)
        subtopic = get_object_or_404(Subtopic, topic=topic, name__iexact=subtopic_name)
        return Task.objects.filter(topic=topic, subtopic=subtopic, published=True).order_by('id')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        topic_name = self.kwargs['quiz_type']
        subtopic_name = self.kwargs['subtopic']
        topic = get_object_or_404(Topic, name__iexact=topic_name)
        subtopic = get_object_or_404(Subtopic, topic=topic, name__iexact=subtopic_name)

        # Определяем предпочитаемый язык (можно сделать динамическим через request.user)
        preferred_language = self.request.user.language if self.request.user.is_authenticated else 'ru'

        # Словарь для "Я не знаю, но хочу узнать!"
        dont_know_option_dict = {
            'ru': "Я не знаю, но хочу узнать",
            'en': "I don't know, but I want to learn",
            'es': "No lo sé, pero quiero aprender",
            'tr': "Bilmiyorum, ama öğrenmek istiyorum",
            'ar': "لا أعرف، ولكن أريد أن أتعلم",
            'fr': "Je ne sais pas, mais je veux apprendre",
            'de': "Ich weiß es nicht, aber ich möchte lernen",
            'hi': "मुझे नहीं पता, लेकिन मैं सीखना चाहता हूँ",
            'fa': "نمی‌دانم، اما می‌خواهم یاد بگیرم",
            'tj': "Ман намедонам, аммо мехоҳам омӯзам",
            'uz': "Bilmayman, lekin o‘rganmoqchiman",
            'kz': "Білмеймін, бірақ үйренгім келеді"
        }

        # Добавляем переводы и перемешанные ответы для каждой задачи
        for task in context['page_obj']:
            # Сначала пытаемся найти перевод на предпочитаемом языке
            translation = TaskTranslation.objects.filter(task=task, language=preferred_language).first()

            # Если перевода на предпочитаемом языке нет, берём первый доступный
            if not translation:
                translation = TaskTranslation.objects.filter(task=task).first()

            # Присваиваем перевод задаче
            task.translation = translation
            if translation:
                # Парсим answers, если это строка JSON
                if isinstance(translation.answers, str):
                    try:
                        answers = json.loads(translation.answers)
                    except json.JSONDecodeError as e:
                        logger.error(f"Ошибка парсинга answers для задачи {task.id}: {e}")
                        answers = []
                else:
                    answers = translation.answers

                # Перемешиваем варианты
                options = answers[:]
                correct_answer = translation.correct_answer
                random.shuffle(options)
                correct_option_id = options.index(correct_answer)

                # Добавляем "Я не знаю, но хочу узнать!" в конец
                dont_know_option = dont_know_option_dict.get(translation.language, "Я не знаю, но хочу узнать")
                options.append(dont_know_option)

                # Присваиваем перемешанные варианты и правильный ответ
                task.answers = options
                task.correct_answer = correct_answer
            else:
                # Если перевода нет, задаём пустые значения
                task.answers = []
                task.correct_answer = None

        context['topic'] = topic
        context['subtopic'] = subtopic
        return context





class UniqueQuizTaskView(DetailView):
    model = Task
    template_name = 'blog/quiz_task_detail.html'
    context_object_name = 'task'

    def get_object(self):
        task_id = self.kwargs.get('task_id')
        logger.info(f"Getting task with ID: {task_id}")
        return Task.objects.get(id=task_id)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        task = self.get_object()
        quiz_type = self.kwargs.get('quiz_type')
        subtopic = self.kwargs.get('subtopic')

        logger.info("=== UniqueQuizTaskView Debug Info ===")
        logger.info(f"Topic: {quiz_type}")
        logger.info(f"Subtopic: {subtopic}")
        logger.info(f"Task ID: {task.id}")
        logger.info(f"Task object: {task}")

        # Получаем перевод
        translation = TaskTranslation.objects.filter(task=task, language="en").first()
        logger.info(f"Translation object: {translation}")

        context['translation'] = translation
        if translation:
            logger.info(f"Translation answers type: {type(translation.answers)}")
            logger.info(f"Raw answers: {translation.answers}")

            if isinstance(translation.answers, str):
                try:
                    context['answers'] = json.loads(translation.answers)
                    logger.info(f"Parsed answers: {context['answers']}")
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing answers JSON: {e}")
                    context['answers'] = []
            else:
                context['answers'] = translation.answers

        # Добавляем информацию о теме и подтеме
        context['topic'] = {'name': quiz_type.capitalize()}
        context['subtopic'] = {'name': subtopic}

        # Формируем URL для отправки ответа
        context['submit_url'] = reverse('blog:submit_task_answer', kwargs={
            'quiz_type': quiz_type,
            'subtopic': subtopic,
            'task_id': task.id
        })
        logger.info(f"Submit URL: {context['submit_url']}")

        # Обрабатываем параметры результата
        is_correct_param = self.request.GET.get('is_correct')
        context['is_correct'] = True if is_correct_param == 'True' else False if is_correct_param == 'False' else None
        context['selected_answer'] = self.request.GET.get('selected')
        context['error'] = self.request.GET.get('error')

        logger.info("=== Context Debug Info ===")
        logger.info(f"is_correct: {context['is_correct']}")
        logger.info(f"selected_answer: {context['selected_answer']}")
        logger.info(f"error: {context['error']}")

        # Проверяем наличие всех необходимых скриптов в контексте
        logger.info("=== Static Files Check ===")
        from django.templatetags.static import static
        script_files = [
            'blog/js/vector.js',
            'blog/js/lightning.js',
            'blog/js/quiz_lightning.js'
        ]
        for script in script_files:
            static_url = static(script)
            logger.info(f"Static URL for {script}: {static_url}")

        return context

    def render_to_response(self, context, **response_kwargs):
        response = super().render_to_response(context, **response_kwargs)
        logger.info("=== Template Rendering ===")
        logger.info(f"Template name: {self.template_name}")
        logger.info(f"Response status code: {response.status_code}")
        return response






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
def send_message(request):
    """
    Отправляет новое сообщение пользователю.

    Принимает содержимое из POST['content'], вложения из request.FILES['attachments'],
    и recipient_username из POST['recipient_username']. Ограничивает размер вложений до 20 МБ.
    Разрешает отправку с пустым текстом, если есть вложения.
    Требует авторизации.
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

    # Проверка размера вложений (20 МБ = 20,971,520 байт)
    max_file_size = 20 * 1024 * 1024  # 20 MB
    for file in files:
        if file.size > max_file_size:
            logger.error(f"send_message: Файл '{file.name}' превышает лимит в 20 МБ")
            return JsonResponse({
                'status': 'error',
                'message': f'Файл "{file.name}" превышает лимит в 20 МБ'
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
    """
    user = request.user

    # Получаем уникальных собеседников
    dialogs = Message.objects.filter(
        Q(sender=user, is_deleted_by_sender=False) | Q(recipient=user, is_deleted_by_recipient=False)
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
        other_user = CustomUser.objects.get(id=other_user_id)
        last_message = Message.objects.get(id=dialog['last_message_id'])
        unread_count = Message.objects.filter(
            recipient=user,
            sender=other_user,
            is_read=False,
            is_deleted_by_recipient=False
        ).count()
        dialog_list.append({
            'user': other_user,
            'last_message': last_message,
            'unread_count': unread_count
        })

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


class MaintenanceView(TemplateView):
    template_name = 'blog/maintenance.html'


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


class AllTestimonialsView(ListView):
    """
    Отображает страницу со всеми одобренными отзывами.

    Attributes:
        template_name (str): Путь к шаблону
        model (Model): Модель для получения данных
        context_object_name (str): Имя переменной контекста для списка отзывов
        paginate_by (int): Количество отзывов на странице
    """
    template_name = 'blog/all_testimonials.html'
    model = Testimonial
    context_object_name = 'testimonials'
    paginate_by = 10

    def get_queryset(self):
        """
        Возвращает QuerySet с одобренными отзывами.

        Returns:
            QuerySet: Отфильтрованный QuerySet с одобренными отзывами,
                     отсортированными по дате создания (сначала новые)
        """
        return Testimonial.objects.filter(is_approved=True).order_by('-created_at')

    def get_context_data(self, **kwargs):
        """
        Добавляет дополнительные данные в контекст шаблона.

        Args:
            **kwargs: Дополнительные именованные аргументы

        Returns:
            dict: Обновленный контекст шаблона
        """
        context = super().get_context_data(**kwargs)
        context['title'] = 'Все отзывы'
        return context

    @method_decorator(login_required)
    def post(self, request, *args, **kwargs):
        """
        Обрабатывает POST-запрос для добавления нового отзыва.

        Args:
            request: HTTP-запрос
            *args: Позиционные аргументы
            **kwargs: Именованные аргументы

        Returns:
            JsonResponse: JSON-ответ с результатом операции
        """
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            text = request.POST.get('text')
            if text:
                Testimonial.objects.create(
                    user=request.user,
                    text=text
                )
                return JsonResponse({'success': True})
        return JsonResponse({'success': False})


