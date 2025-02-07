from django.shortcuts import render, get_object_or_404, redirect
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from .models import Category, Post, Project, Message, MessageAttachment
from .serializers import CategorySerializer, PostSerializer, ProjectSerializer
from rest_framework.views import APIView
from django.views.generic import TemplateView, DetailView
from django.core.paginator import Paginator
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, FileResponse, HttpResponseNotFound
from accounts.models import CustomUser, Profile
from django.db.models import Q
from django.views.decorators.http import require_POST
from django.contrib.auth.forms import PasswordChangeForm
from django.core.exceptions import PermissionDenied
import json
from .forms import ProfileEditForm, PersonalInfoForm
from django.contrib.auth import get_user_model
import os
from django.conf import settings
from django.template import loader
from django.templatetags.static import static
from django.template import TemplateDoesNotExist
from django.template.loader import get_template
from django.db.models import Count, Avg
from django.db.models.functions import TruncDate
from datetime import datetime, timedelta
from tasks.models import Task, TaskStatistics
from topics.models import Topic

# Create your views here.

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    lookup_field = 'slug'

class PostViewSet(viewsets.ModelViewSet):
    queryset = Post.objects.all()
    serializer_class = PostSerializer
    lookup_field = 'slug'
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'content']
    ordering_fields = ['created_at', 'views_count']

    def get_queryset(self):
        if self.action == 'list':
            return Post.objects.filter(published=True)
        return Post.objects.all()

    @action(detail=True, methods=['post'])
    def increment_views(self, request, slug=None):
        post = self.get_object()
        post.views_count += 1
        post.save()
        return Response({'views_count': post.views_count})

    def perform_create(self, serializer):
        if serializer.validated_data.get('published', False):
            serializer.validated_data['published_at'] = timezone.now()
        serializer.save()

class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    lookup_field = 'slug'
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description', 'technologies']
    ordering_fields = ['created_at']

    @action(detail=False, methods=['get'])
    def featured(self, request):
        featured_projects = Project.objects.filter(featured=True)
        serializer = self.get_serializer(featured_projects, many=True)
        return Response(serializer.data)

class HomePageView(TemplateView):
    template_name = 'blog/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Добавляем посты для блога
        posts_list = Post.objects.all()
        paginator = Paginator(posts_list, 5)
        page = self.request.GET.get('page')
        context['posts'] = paginator.get_page(page)
        
        # Добавляем только категории блога
        context['categories'] = Category.objects.filter(is_portfolio=False)
        
        # Добавляем проекты и их категории
        context['projects'] = Project.objects.all()
        context['portfolio_categories'] = Category.objects.filter(is_portfolio=True)
        
        return context


class AboutView(TemplateView):
    template_name = 'blog/about.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Добавляем необходимый контекст
        return context


class PostDetailView(DetailView):
    model = Post
    template_name = 'blog/post_detail.html'
    context_object_name = 'post'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user'] = self.request.user
        # Добавляем остальной контекст
        context['categories'] = Category.objects.all()
        context['posts'] = Post.objects.all()[:5]  # Последние 5 постов для сайдбара
        return context

class ProjectDetailView(DetailView):
    model = Project
    template_name = 'blog/project_detail.html'
    context_object_name = 'project'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user'] = self.request.user
        # Добавляем остальной контекст
        context['categories'] = Category.objects.all()
        context['projects'] = Project.objects.all()[:5]  # Последние 5 проектов для сайдбара
        return context

def blog_view(request):
    category_slug = request.GET.get('category')
    posts_list = Post.objects.all()
    
    if category_slug:
        posts_list = posts_list.filter(category__slug=category_slug)
    
    # Пагинация
    paginator = Paginator(posts_list, 5)  # 5 постов на страницу
    page = request.GET.get('page')
    posts = paginator.get_page(page)
    
    # Получаем все категории
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
        # Добавляем необходимый контекст
        return context

class PortfolioView(TemplateView):
    template_name = 'blog/portfolio.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['projects'] = Project.objects.all()
        context['portfolio_categories'] = Category.objects.filter(is_portfolio=True)
        return context

class BlogView(TemplateView):
    template_name = 'blog/blog_page.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        posts_list = Post.objects.all()
        paginator = Paginator(posts_list, 5)  # 5 постов на страницу
        page = self.request.GET.get('page')
        context['posts'] = paginator.get_page(page)
        context['categories'] = Category.objects.filter(is_portfolio=False)
        return context



class ContactView(TemplateView):
    template_name = 'blog/contact.html'

class QuizesView(TemplateView):
    template_name = 'blog/quizes.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Здесь будем добавлять контекст для квизов
        return context

class QuizDetailView(TemplateView):
    template_name = 'blog/quiz_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        quiz_type = kwargs.get('quiz_type')
        context['quiz_type'] = quiz_type.title()
        return context

class ProfileView(TemplateView):
    template_name = 'blog/profile.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user_profile'] = self.request.user
        return context

@login_required
def dashboard_view(request):
    """Личный кабинет пользователя"""
    print("\nDebug dashboard view:")
    print(f"User: {request.user}")
    
    # Получаем статистику
    stats = {
        'total_attempts': TaskStatistics.objects.filter(user=request.user).count(),
        'successful_attempts': TaskStatistics.objects.filter(user=request.user, successful=True).count(),
    }
    
    # Вычисляем процент успешности
    if stats['total_attempts'] > 0:
        stats['success_rate'] = round((stats['successful_attempts'] / stats['total_attempts']) * 100, 1)
    else:
        stats['success_rate'] = 0
    
    # Получаем сообщения для вкладки сообщений
    inbox_messages = Message.objects.filter(recipient=request.user).order_by('-created_at')
    sent_messages = Message.objects.filter(sender=request.user).order_by('-created_at')
    
    context = {
        'stats': stats,
        'chart_data': get_user_chart_data(request.user),
        'inbox_messages': inbox_messages,
        'sent_messages': sent_messages,
        'personal_info_form': PersonalInfoForm(instance=request.user.profile, user=request.user),
        'is_owner': True
    }
    
    return render(request, 'blog/dashboard.html', context)

def profile_view(request, username):
    """Просмотр профиля пользователя"""
    profile_user = get_object_or_404(CustomUser, username=username)
    is_owner = request.user == profile_user
    
    # Получаем статистику
    stats = {
        'total_attempts': TaskStatistics.objects.filter(user=profile_user).count(),
        'successful_attempts': TaskStatistics.objects.filter(user=profile_user, successful=True).count(),
    }
    
    if stats['total_attempts'] > 0:
        stats['success_rate'] = round((stats['successful_attempts'] / stats['total_attempts']) * 100, 1)
    else:
        stats['success_rate'] = 0
    
    context = {
        'profile_user': profile_user,
        'stats': stats,
        'chart_data': get_user_chart_data(profile_user),
        'is_owner': is_owner
    }
    
    return render(request, 'blog/profile.html', context)

def get_user_chart_data(user):
    """Получение данных для графиков"""
    # Статистика активности за последние 30 дней
    last_30_days = timezone.now() - timezone.timedelta(days=30)
    activity_stats = TaskStatistics.objects.filter(
        user=user,
        last_attempt_date__gte=last_30_days
    ).annotate(
        date=TruncDate('last_attempt_date')
    ).values('date').annotate(
        attempts=Count('id'),
        successful=Count('id', filter=Q(successful=True))
    ).order_by('date')
    
    # Статистика по темам
    topic_stats = TaskStatistics.objects.filter(user=user).values(
        'task__topic__name'
    ).annotate(
        total=Count('id'),
        successful=Count('id', filter=Q(successful=True))
    ).order_by('-total')[:5]
    
    # Статистика по сложности
    difficulty_stats = TaskStatistics.objects.filter(user=user).values(
        'task__difficulty'
    ).annotate(
        total=Count('id'),
        successful=Count('id', filter=Q(successful=True))
    )
    
    return {
        'activity': {
            'labels': [stat['date'].strftime('%d.%m') for stat in activity_stats],
            'attempts': [stat['attempts'] for stat in activity_stats],
            'successful': [stat['successful'] for stat in activity_stats]
        },
        'topics': {
            'labels': [stat['task__topic__name'] for stat in topic_stats],
            'success_rates': [
                round((stat['successful'] / stat['total']) * 100 if stat['total'] > 0 else 0, 1)
                for stat in topic_stats
            ]
        },
        'difficulty': {
            'labels': [stat['task__difficulty'] for stat in difficulty_stats],
            'success_rates': [
                round((stat['successful'] / stat['total']) * 100 if stat['total'] > 0 else 0, 1)
                for stat in difficulty_stats
            ]
        }
    }

@login_required
@require_POST
def update_settings(request):
    try:
        data = json.loads(request.body)
        setting = data.get('setting')
        value = data.get('value')
        
        profile = request.user.profile
        
        if setting == 'email_notifications':
            profile.email_notifications = value
        elif setting == 'is_public':
            profile.is_public = value
        elif setting == 'theme_preference':
            profile.theme_preference = 'dark' if value else 'light'
        else:
            return JsonResponse({'status': 'error', 'message': 'Invalid setting'}, status=400)
        
        profile.save()
        return JsonResponse({'status': 'success'})
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@require_POST
def delete_message(request, message_id):
    message = get_object_or_404(Message, id=message_id)
    if request.user not in [message.recipient, message.sender]:
        return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)
    
    # Мягкое удаление
    message.soft_delete(request.user)
    
    # Если сообщение полностью удалено обоими пользователями
    if message.is_completely_deleted:
        # Удаляем вложения
        for attachment in message.attachments.all():
            if attachment.file:
                attachment.file.delete()  # Удаляем физический файл
            attachment.delete()
        message.delete()  # Удаляем само сообщение
    
    return JsonResponse({'status': 'success'})

@login_required
@require_POST
def send_message(request, recipient_username):
    recipient = get_object_or_404(CustomUser, username=recipient_username)
    content = request.POST.get('content')
    
    if content:
        message = Message.objects.create(
            sender=request.user,
            recipient=recipient,
            content=content
        )
        
        # Обработка вложений
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
    attachment = get_object_or_404(MessageAttachment, id=attachment_id)
    message = attachment.message
    
    if request.user not in [message.sender, message.recipient]:
        raise PermissionDenied
        
    response = FileResponse(attachment.file)
    response['Content-Disposition'] = f'attachment; filename="{attachment.filename}"'
    return response

@login_required
def inbox(request):
    # Помечаем все сообщения как прочитанные при открытии inbox
    Message.objects.filter(
        recipient=request.user,
        is_read=False,
        is_deleted_by_recipient=False
    ).update(is_read=True)
    
    # Получаем входящие и исходящие сообщения
    incoming_messages = Message.objects.filter(
        recipient=request.user,
        is_deleted_by_recipient=False
    ).select_related('sender').prefetch_related('attachments')
    
    outgoing_messages = Message.objects.filter(
        sender=request.user,
        is_deleted_by_sender=False
    ).select_related('recipient').prefetch_related('attachments')
    
    return render(request, 'blog/inbox.html', {
        'incoming_messages': incoming_messages,
        'outgoing_messages': outgoing_messages
    })

@login_required
def get_unread_messages_count(request):
    count = Message.objects.filter(recipient=request.user, is_read=False).count()
    return JsonResponse({'count': count})

def index(request):
    User = get_user_model()
    context = {
        'users': User.objects.exclude(is_staff=True).select_related('profile').order_by('-date_joined')
    }
    return render(request, 'blog/index.html', context)



def custom_404(request, exception=None):
    return redirect('404')



def statistics_view(request):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    context = {
        'total_users': CustomUser.objects.count(),
        'total_quizzes_completed': TaskStatistics.objects.count(),
        'avg_score': TaskStatistics.objects.filter(successful=True).count() * 100.0 / TaskStatistics.objects.count() if TaskStatistics.objects.exists() else 0,
        
        # Данные для графика активности
        'activity_dates': json.dumps([
            date.strftime('%d.%m')
            for date in (start_date + timedelta(n) for n in range(31))
        ]),
        'activity_data': json.dumps(
            list(TaskStatistics.objects.filter(
                last_attempt_date__gte=start_date
            ).annotate(
                date=TruncDate('last_attempt_date')
            ).values('date').annotate(
                count=Count('id')
            ).values_list('count', flat=True))
        ),
        
        # Данные для графика категорий (по темам)
        'categories_labels': json.dumps(
            list(Topic.objects.annotate(
                task_count=Count('tasks')
            ).values_list('name', flat=True))
        ),
        'categories_data': json.dumps(
            list(Topic.objects.annotate(
                task_count=Count('tasks')
            ).values_list('task_count', flat=True))
        ),
        
        # Данные для распределения успешности
        'scores_distribution': json.dumps([
            TaskStatistics.objects.filter(
                attempts__gt=0,
                attempts__lte=i+5
            ).count() for i in range(0, 25, 5)
        ])
    }
    
    return render(request, 'blog/statistics.html', context)

@login_required
def dashboard_view(request):
    """Личный кабинет пользователя"""
    print("\nDebug dashboard view:")
    print(f"User: {request.user}")
    
    # Получаем статистику
    stats = {
        'total_attempts': TaskStatistics.objects.filter(user=request.user).count(),
        'successful_attempts': TaskStatistics.objects.filter(user=request.user, successful=True).count(),
    }
    
    # Вычисляем процент успешности
    if stats['total_attempts'] > 0:
        stats['success_rate'] = round((stats['successful_attempts'] / stats['total_attempts']) * 100, 1)
    else:
        stats['success_rate'] = 0
    
    # Получаем сообщения для вкладки сообщений
    inbox_messages = Message.objects.filter(recipient=request.user).order_by('-created_at')
    sent_messages = Message.objects.filter(sender=request.user).order_by('-created_at')
    
    context = {
        'stats': stats,
        'chart_data': get_user_chart_data(request.user),
        'inbox_messages': inbox_messages,
        'sent_messages': sent_messages,
        'personal_info_form': PersonalInfoForm(instance=request.user.profile, user=request.user),
        'is_owner': True
    }
    
    return render(request, 'blog/dashboard.html', context)

def profile_view(request, username):
    """Просмотр профиля пользователя"""
    profile_user = get_object_or_404(CustomUser, username=username)
    is_owner = request.user == profile_user
    
    # Получаем статистику
    stats = {
        'total_attempts': TaskStatistics.objects.filter(user=profile_user).count(),
        'successful_attempts': TaskStatistics.objects.filter(user=profile_user, successful=True).count(),
    }
    
    if stats['total_attempts'] > 0:
        stats['success_rate'] = round((stats['successful_attempts'] / stats['total_attempts']) * 100, 1)
    else:
        stats['success_rate'] = 0
    
    context = {
        'profile_user': profile_user,
        'stats': stats,
        'chart_data': get_user_chart_data(profile_user),
        'is_owner': is_owner
    }
    
    return render(request, 'blog/profile.html', context)

def get_user_chart_data(user):
    """Получение данных для графиков"""
    # Статистика активности за последние 30 дней
    last_30_days = timezone.now() - timezone.timedelta(days=30)
    activity_stats = TaskStatistics.objects.filter(
        user=user,
        last_attempt_date__gte=last_30_days
    ).annotate(
        date=TruncDate('last_attempt_date')
    ).values('date').annotate(
        attempts=Count('id'),
        successful=Count('id', filter=Q(successful=True))
    ).order_by('date')
    
    # Статистика по темам
    topic_stats = TaskStatistics.objects.filter(user=user).values(
        'task__topic__name'
    ).annotate(
        total=Count('id'),
        successful=Count('id', filter=Q(successful=True))
    ).order_by('-total')[:5]
    
    # Статистика по сложности
    difficulty_stats = TaskStatistics.objects.filter(user=user).values(
        'task__difficulty'
    ).annotate(
        total=Count('id'),
        successful=Count('id', filter=Q(successful=True))
    )
    
    return {
        'activity': {
            'labels': [stat['date'].strftime('%d.%m') for stat in activity_stats],
            'attempts': [stat['attempts'] for stat in activity_stats],
            'successful': [stat['successful'] for stat in activity_stats]
        },
        'topics': {
            'labels': [stat['task__topic__name'] for stat in topic_stats],
            'success_rates': [
                round((stat['successful'] / stat['total']) * 100 if stat['total'] > 0 else 0, 1)
                for stat in topic_stats
            ]
        },
        'difficulty': {
            'labels': [stat['task__difficulty'] for stat in difficulty_stats],
            'success_rates': [
                round((stat['successful'] / stat['total']) * 100 if stat['total'] > 0 else 0, 1)
                for stat in difficulty_stats
            ]
        }
    }
