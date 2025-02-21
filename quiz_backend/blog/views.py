import json
from datetime import datetime, timedelta

from accounts.models import CustomUser
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.http import JsonResponse, FileResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView, DetailView
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from tasks.models import Task, TaskStatistics
from topics.models import Topic

from .models import Category, Post, Project, Message, MessageAttachment
from .serializers import CategorySerializer, PostSerializer, ProjectSerializer




class CategoryViewSet(viewsets.ModelViewSet):
    """
    ViewSet для модели Category,
    обеспечивает стандартный набор операций через REST:
    list, create, retrieve, update, destroy.
    lookup_field = 'slug', значит поиск по slug, а не по id.
    """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    lookup_field = 'slug'


class PostViewSet(viewsets.ModelViewSet):
    """
    ViewSet для модели Post,
    содержит CRUD-операции, а также поиск, сортировку и метод increment_views.
    """
    queryset = Post.objects.all()
    serializer_class = PostSerializer
    lookup_field = 'slug'
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'content']
    ordering_fields = ['created_at', 'views_count']

    def get_queryset(self):
        """
        Если запрашивается список (list), то выдаём только опубликованные (published=True),
        иначе возвращаем все посты.
        """
        if self.action == 'list':
            return Post.objects.filter(published=True)
        return Post.objects.all()

    @action(detail=True, methods=['post'])
    def increment_views(self, request, slug=None):
        """
        Дополнительный метод POST /posts/<slug>/increment_views/
        увеличивает счётчик просмотров и возвращает актуальное значение.
        """
        post = self.get_object()
        post.views_count += 1
        post.save()
        return Response({'views_count': post.views_count})

    def perform_create(self, serializer):
        """
        При создании, если published=True, автоматически ставим published_at = сейчас.
        """
        if serializer.validated_data.get('published', False):
            serializer.validated_data['published_at'] = timezone.now()
        serializer.save()


class ProjectViewSet(viewsets.ModelViewSet):
    """
    ViewSet для модели Project,
    даёт CRUD, поиск, сортировку.
    Имеет кастомный метод featured (GET /projects/featured/).
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
        Возвращает JSON со всеми Project, где featured=True.
        """
        featured_projects = Project.objects.filter(featured=True)
        serializer = self.get_serializer(featured_projects, many=True)
        return Response(serializer.data)


class HomePageView(TemplateView):
    """
    Класс-представление для главной страницы (template = blog/index.html).
    Загружает все посты с пагинацией, а также категории/проекты.
    """
    template_name = 'blog/index.html'

    def get_context_data(self, **kwargs):
        """
        В контекст добавляем:
        - posts: Пагинированный список Post (по 5 на страницу)
        - categories: Категории, не являющиеся портфолио
        - projects: Все проекты
        - portfolio_categories: Категории с is_portfolio=True
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
    Отображает страницу "About" (blog/about.html).
    """
    template_name = 'blog/about.html'

    def get_context_data(self, **kwargs):
        """
        Можно расширять контекст при необходимости.
        """
        context = super().get_context_data(**kwargs)
        return context


class PostDetailView(DetailView):
    """
    DetailView для модели Post, шаблон blog/post_detail.html.
    Показывает отдельный пост.
    """
    model = Post
    template_name = 'blog/post_detail.html'
    context_object_name = 'post'

    def get_context_data(self, **kwargs):
        """
        В контекст:
        - self.request.user
        - все категории
        - последние 5 постов
        """
        context = super().get_context_data(**kwargs)
        context['user'] = self.request.user
        context['categories'] = Category.objects.all()
        context['posts'] = Post.objects.all()[:5]
        return context


class ProjectDetailView(DetailView):
    """
    DetailView для модели Project,
    отображает проект в blog/project_detail.html.
    """
    model = Project
    template_name = 'blog/project_detail.html'
    context_object_name = 'project'

    def get_context_data(self, **kwargs):
        """
        В контекст:
        - self.request.user
        - все категории
        - последние 5 проектов
        """
        context = super().get_context_data(**kwargs)
        context['user'] = self.request.user
        context['categories'] = Category.objects.all()
        context['projects'] = Project.objects.all()[:5]
        return context


def blog_view(request):
    """
    Функциональное представление для blog/blog.html:
    - фильтрация по категории (GET['category'])
    - пагинация по 5 постов
    - категории (не портфолио) в контексте
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
    Страница резюме (blog/resume.html).
    """
    template_name = 'blog/resume.html'

    def get_context_data(self, **kwargs):
        """
        Можно добавлять нужный контекст, если требуется.
        """
        context = super().get_context_data(**kwargs)
        return context


class PortfolioView(TemplateView):
    """
    Страница портфолио (blog/portfolio.html).
    Показывает Projects и portfolio_categories.
    """
    template_name = 'blog/portfolio.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['projects'] = Project.objects.all()
        context['portfolio_categories'] = Category.objects.filter(is_portfolio=True)
        return context


class BlogView(TemplateView):
    """
    Аналог blog_view, но реализован через TemplateView (blog/blog_page.html).
    Делает пагинацию по 5 постов, добавляет категории is_portfolio=False.
    """
    template_name = 'blog/blog_page.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        posts_list = Post.objects.all()
        paginator = Paginator(posts_list, 5)
        page = self.request.GET.get('page')
        context['posts'] = paginator.get_page(page)
        context['categories'] = Category.objects.filter(is_portfolio=False)
        return context


class ContactView(TemplateView):
    """
    Страница "Contact" (blog/contact.html).
    """
    template_name = 'blog/contact.html'


class QuizesView(TemplateView):
    """
    Страница "Quizes" (blog/quizes.html),
    потенциально для отображения списка викторин.
    """
    template_name = 'blog/quizes.html'

    def get_context_data(self, **kwargs):
        """
        Здесь можно добавлять данные о квизах в контекст.
        """
        context = super().get_context_data(**kwargs)
        return context


class QuizDetailView(TemplateView):
    """
    Страница отдельного квиза (blog/quiz_detail.html).
    Принимает quiz_type из URL.
    """
    template_name = 'blog/quiz_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        quiz_type = kwargs.get('quiz_type')
        context['quiz_type'] = quiz_type.title()
        return context




@login_required
@require_POST
def delete_message(request, message_id):
    """
    Мягкое удаление сообщения (Message).
    Если оба юзера удалили, сообщение с вложениями удаляется окончательно.
    """
    message = get_object_or_404(Message, id=message_id)
    if request.user not in [message.recipient, message.sender]:
        return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)

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
    Отправка сообщения (Message) пользователю recipient_username.
    Содержимое берётся из POST['content'], вложения - из request.FILES['attachments'].
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

    return JsonResponse({'status': 'error', 'message': 'Content is required'}, status=400)


@login_required
def download_attachment(request, attachment_id):
    """
    Скачивание вложения. Проверяем, что пользователь -
    либо отправитель, либо получатель.
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
    Показ входящих / исходящих сообщений в blog/inbox.html.
    Все непрочитанные для текущего юзера становятся прочитанными.
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
    Возвращает число непрочитанных сообщений текущего юзера в JSON.
    """
    count = Message.objects.filter(recipient=request.user, is_read=False).count()
    return JsonResponse({'count': count})


def index(request):
    """
    Ещё одно представление главной (blog/index.html),
    передаёт в контекст всех пользователей (не staff).
    """
    User = get_user_model()
    context = {
        'users': User.objects.exclude(is_staff=True).select_related('profile').order_by('-date_joined')
    }
    return render(request, 'blog/index.html', context)




def custom_404(request, exception=None):
    """
    Кастомный обработчик 404: редиректит на '404'.
    """
    return redirect('404')




def statistics_view(request):
    """
    Статистика по квизам/пользователям (используется шаблон accounts/statistics.html).
    Вычисляет общие показатели:
      - total_users
      - total_quizzes_completed
      - avg_score
    и массивы данных для графиков.

    Если GET-параметр view=personal передан и пользователь авторизован,
    выбирается первая запись статистики для пользователя (через .first())
    и в контекст добавляется словарь с личной статистикой (ключ user_stats).
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
            stats = request.user.statistics.first()  # Возвращает первую запись статистики пользователя
        except AttributeError:
            stats = None

        if stats:
            # Здесь вы можете настроить логику агрегации статистики.
            # В данном примере для простоты считаем:
            context['user_stats'] = {
                'successful_attempts': 1 if stats.successful else 0,  # упрощённо
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