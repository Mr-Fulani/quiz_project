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
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.core.exceptions import PermissionDenied
import json
from .forms import ProfileEditForm
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
def profile_view(request, username):
    # Получаем пользователя по имени
    user = get_object_or_404(CustomUser, username=username)
    profile = user.profile

    # Проверяем, является ли текущий пользователь владельцем профиля
    is_owner = (user == request.user)

    context = {
        'profile_user': user,
        'profile': profile,
        'is_owner': is_owner,
    }
    return render(request, 'blog/profile.html', context)

@login_required
def edit_profile(request):
    if request.method == 'POST':
        form = ProfileEditForm(request.POST, request.FILES, instance=request.user.profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('blog:profile', username=request.user.username)
    else:
        form = ProfileEditForm(instance=request.user.profile)
    
    return render(request, 'blog/edit_profile.html', {'form': form})

@login_required
def profile_stats(request, username):
    """API endpoint для получения статистики пользователя"""
    user = get_object_or_404(CustomUser, username=username)
    profile = user.profile
    
    stats = {
        'total_points': profile.total_points,
        'quizzes_completed': profile.quizzes_completed,
        'average_score': profile.average_score,
        'favorite_category': profile.favorite_category,
    }
    
    return JsonResponse(stats)

@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Your password was successfully updated!')
            return redirect('blog:profile', username=request.user.username)
        else:
            messages.error(request, 'Please correct the errors below.')
            return JsonResponse({
                'status': 'error',
                'errors': form.errors
            }, status=400)
    return redirect('blog:profile', username=request.user.username)

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
def send_message(request, recipient_username):
    if request.method == 'POST':
        recipient = get_object_or_404(CustomUser, username=recipient_username)
        content = request.POST.get('content')
        
        if content:
            Message.objects.create(
                sender=request.user,
                recipient=recipient,
                content=content
            )
            messages.success(request, 'Message sent successfully!')
        else:
            messages.error(request, 'Message cannot be empty!')
            
    return redirect('blog:profile', username=recipient_username)

@login_required
def delete_message(request, message_id):
    message = get_object_or_404(Message, id=message_id)
    if request.user not in [message.sender, message.recipient]:
        raise PermissionDenied
    
    message.soft_delete(request.user)
    
    if message.is_completely_deleted:
        # Удаляем файлы и сообщение полностью
        for attachment in message.attachments.all():
            if attachment.file:
                attachment.file.delete()
        message.delete()
        return JsonResponse({'status': 'deleted'})
    
    return JsonResponse({'status': 'soft_deleted'})

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
    user_messages = Message.objects.filter(recipient=request.user)
    return render(request, 'blog/inbox.html', {'messages': user_messages})

@login_required
def mark_as_read(request, message_id):
    message = get_object_or_404(Message, id=message_id, recipient=request.user)
    message.is_read = True
    message.save()
    return JsonResponse({'status': 'success'})

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
