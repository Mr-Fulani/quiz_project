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
from django.db.models import Count, F, Q, Max, Prefetch, Subquery, OuterRef
import logging

logger = logging.getLogger(__name__)
from django.db.models.functions import TruncDate
from django.http import JsonResponse, FileResponse, Http404, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _, get_language, activate
from django.utils import translation
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
from accounts.serializers import ProfileSerializer, SocialLinksSerializer

from .forms import (ContactForm, PostForm, ProjectForm, TestimonialForm,
                    TaskFilterForm)


logger = logging.getLogger(__name__)


def custom_set_language(request):
    """
    Кастомный view для переключения языка через URL-параметры.
    Работает в режиме инкогнито, так как не зависит от куки.
    """
    if request.method == 'POST':
        language = request.POST.get('language')
    else:
        language = request.GET.get('language')
    
    if language and language in [lang[0] for lang in settings.LANGUAGES]:
        # Активируем язык для текущего запроса
        activate(language)
        
        # Получаем referer (откуда пришел запрос) или используем текущий путь
        referer = request.META.get('HTTP_REFERER')
        if referer:
            # Извлекаем путь из referer
            from urllib.parse import urlparse
            parsed_url = urlparse(referer)
            current_path = parsed_url.path
        else:
            # Если нет referer, используем текущий путь
            current_path = request.path
        
        # Убираем /set-language/ из пути если он есть
        if current_path.startswith('/set-language/'):
            current_path = '/'
        
        path_parts = current_path.split('/')
        
        # Убираем языковой префикс если он есть
        if len(path_parts) > 1 and path_parts[1] in [lang[0] for lang in settings.LANGUAGES]:
            path_parts = path_parts[2:]  # Убираем пустой элемент и языковой префикс
        else:
            path_parts = path_parts[1:]  # Убираем только пустой элемент
        
        # Собираем новый путь с новым языковым префиксом
        new_path = f'/{language}/'
        if path_parts:
            new_path += '/'.join(path_parts)
        
        # Добавляем trailing slash если нужно
        if current_path.endswith('/') and not new_path.endswith('/'):
            new_path += '/'
        
        return HttpResponseRedirect(new_path)
    
    # Если язык не указан или неверный, редиректим на язык по умолчанию
    return HttpResponseRedirect(f'/{settings.LANGUAGE_CODE}/')



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
        Увеличивает счётчик просмотров поста (только уникальные).

        Метод доступен по POST-запросу на /posts/<slug>/increment_views/.
        Возвращает обновлённое количество просмотров в JSON.
        """
        from .models import PostView
        from datetime import datetime, timedelta
        from django.utils import timezone
        
        post = self.get_object()
        
        # Получаем IP адрес
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        user = request.user if request.user.is_authenticated else None
        
        # Проверяем, был ли просмотр в последние 24 часа
        yesterday = timezone.now() - timedelta(hours=24)
        
        existing_view = None
        if user:
            existing_view = PostView.objects.filter(
                post=post,
                user=user,
                created_at__gte=yesterday
            ).first()
        else:
            existing_view = PostView.objects.filter(
                post=post,
                ip_address=ip,
                created_at__gte=yesterday
            ).first()
        
        if not existing_view:
            # Создаем новый просмотр
            PostView.objects.create(
                post=post,
                user=user,
                ip_address=ip,
                user_agent=user_agent
            )
            
            # Увеличиваем счетчик
            post.views_count += 1
            post.save()
        
        return Response({'views_count': post.views_count})

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def toggle_like(self, request, slug=None):
        """
        Переключает лайк для поста.

        Если пользователь уже лайкнул пост, убирает лайк.
        Если не лайкнул, добавляет лайк.
        """
        from .models import PostLike
        post = self.get_object()
        like, created = PostLike.objects.get_or_create(
            user=request.user,
            post=post
        )
        
        if not created:
            like.delete()
            liked = False
        else:
            liked = True
            
        return Response({
            'liked': liked,
            'likes_count': post.get_likes_count()
        })

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def share(self, request, slug=None):
        """
        Создает репост поста.
        Требует авторизации для сохранения уникальной статистики с аватарами пользователей.
        """
        from .models import PostShare
        post = self.get_object()
        platform = request.data.get('platform', 'other')
        shared_url = request.data.get('shared_url', '')
        
        # Сохраняем репост только для авторизованных пользователей
        user = request.user
        
        # Создаем или получаем существующий репост (один репост на пользователя на платформе)
        share, created = PostShare.objects.get_or_create(
            user=user,
            post=post,
            platform=platform,
            defaults={'shared_url': shared_url}
        )
        
        # Если репост уже существует, обновляем URL
        if not created and shared_url:
            share.shared_url = shared_url
            share.save()
        
        return Response({
            'shared': True,
            'shares_count': post.get_shares_count()
        })

    @action(detail=True, methods=['get'])
    def likes_users(self, request, slug=None):
        """
        Возвращает список пользователей, которые лайкнули пост.
        """
        post = self.get_object()
        # Ограничиваем до 3 последних лайков для быстрой загрузки
        likes = post.likes.select_related('user').order_by('-created_at')[:3]
        
        users_data = []
        for like in likes:
            users_data.append({
                'username': like.user.username,
                'full_name': f"{like.user.first_name} {like.user.last_name}".strip() or like.user.username,
                'avatar': like.user.avatar.url if like.user.avatar else '/static/blog/images/avatar/default_avatar.png',
                'created_at': like.created_at.isoformat()
            })
        
        return Response({
            'users': users_data,
            'total_count': post.get_likes_count()
        })

    @action(detail=True, methods=['get'])
    def shares_users(self, request, slug=None):
        """
        Возвращает список пользователей, которые поделились постом.
        """
        post = self.get_object()
        # Ограничиваем до 3 последних репостов для быстрой загрузки
        shares = post.shares.select_related('user').filter(user__isnull=False).order_by('-created_at')[:3]
        
        users_data = []
        for share in shares:
            users_data.append({
                'username': share.user.username,
                'full_name': f"{share.user.first_name} {share.user.last_name}".strip() or share.user.username,
                'avatar': share.user.avatar.url if share.user.avatar else '/static/blog/images/avatar/default_avatar.png',
                'platform': share.platform,
                'created_at': share.created_at.isoformat()
            })
        
        return Response({
            'users': users_data,
            'total_count': post.get_shares_count()
        })

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

    @action(detail=True, methods=['post'])
    def increment_views(self, request, slug=None):
        """
        Увеличивает счётчик просмотров проекта (только уникальные).

        Метод доступен по POST-запросу на /projects/<slug>/increment_views/.
        Возвращает обновлённое количество просмотров в JSON.
        """
        from .models import ProjectView
        from datetime import datetime, timedelta
        from django.utils import timezone
        
        project = self.get_object()
        
        # Получаем IP адрес
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        user = request.user if request.user.is_authenticated else None
        
        # Проверяем, был ли просмотр в последние 24 часа
        yesterday = timezone.now() - timedelta(hours=24)
        
        existing_view = None
        if user:
            existing_view = ProjectView.objects.filter(
                project=project,
                user=user,
                created_at__gte=yesterday
            ).first()
        else:
            existing_view = ProjectView.objects.filter(
                project=project,
                ip_address=ip,
                created_at__gte=yesterday
            ).first()
        
        if not existing_view:
            # Создаем новый просмотр
            ProjectView.objects.create(
                project=project,
                user=user,
                ip_address=ip,
                user_agent=user_agent
            )
            
            # Увеличиваем счетчик
            project.views_count += 1
            project.save()
        
        return Response({'views_count': project.views_count})

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def toggle_like(self, request, slug=None):
        """
        Переключает лайк для проекта.

        Если пользователь уже лайкнул проект, убирает лайк.
        Если не лайкнул, добавляет лайк.
        """
        from .models import ProjectLike
        project = self.get_object()
        like, created = ProjectLike.objects.get_or_create(
            user=request.user,
            project=project
        )
        
        if not created:
            like.delete()
            liked = False
        else:
            liked = True
            
        return Response({
            'liked': liked,
            'likes_count': project.get_likes_count()
        })

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def share(self, request, slug=None):
        """
        Создает репост проекта.
        Требует авторизации для сохранения уникальной статистики с аватарами пользователей.
        """
        from .models import ProjectShare
        project = self.get_object()
        platform = request.data.get('platform', 'other')
        shared_url = request.data.get('shared_url', '')
        
        # Сохраняем репост только для авторизованных пользователей
        user = request.user
        
        # Создаем или получаем существующий репост (один репост на пользователя на платформе)
        share, created = ProjectShare.objects.get_or_create(
            user=user,
            project=project,
            platform=platform,
            defaults={'shared_url': shared_url}
        )
        
        # Если репост уже существует, обновляем URL
        if not created and shared_url:
            share.shared_url = shared_url
            share.save()
        
        return Response({
            'shared': True,
            'shares_count': project.get_shares_count()
        })

    @action(detail=True, methods=['get'])
    def likes_users(self, request, slug=None):
        """
        Возвращает список пользователей, которые лайкнули проект.
        """
        project = self.get_object()
        likes = project.likes.select_related('user').order_by('-created_at')[:10]  # Последние 10 лайков
        
        users_data = []
        for like in likes:
            users_data.append({
                'username': like.user.username,
                'full_name': f"{like.user.first_name} {like.user.last_name}".strip() or like.user.username,
                'avatar': like.user.avatar.url if like.user.avatar else '/static/blog/images/avatar/default_avatar.png',
                'created_at': like.created_at.isoformat()
            })
        
        return Response({
            'users': users_data,
            'total_count': project.get_likes_count()
        })

    @action(detail=True, methods=['get'])
    def shares_users(self, request, slug=None):
        """
        Возвращает список пользователей, которые поделились проектом.
        """
        project = self.get_object()
        shares = project.shares.select_related('user').order_by('-created_at')[:10]  # Последние 10 репостов
        
        users_data = []
        for share in shares:
            # Пропускаем записи без пользователя (анонимные репосты)
            if share.user is None:
                continue
                
            users_data.append({
                'username': share.user.username,
                'full_name': f"{share.user.first_name} {share.user.last_name}".strip() or share.user.username,
                'avatar': share.user.avatar.url if share.user.avatar else '/static/blog/images/avatar/default_avatar.png',
                'platform': share.platform,
                'created_at': share.created_at.isoformat()
            })
        
        return Response({
            'users': users_data,
            'total_count': project.get_shares_count()
        })


class HomePageView(BreadcrumbsMixin, TemplateView):
    """
    Отображает главную страницу сайта.
    Использует шаблон blog/index.html, предоставляет пагинированный список постов,
    категории, проекты, видео.
    """
    template_name = 'blog/index.html'
    breadcrumbs = [{'name': _('Главная'), 'url': reverse_lazy('blog:home')}]

    def dispatch(self, request, *args, **kwargs):
        """
        Обрабатываем данные от Telegram в URL параметрах.
        Telegram может делать redirect на главную страницу вместо /api/social-auth/telegram/auth/
        """
        # Проверяем наличие данных от Telegram в GET параметрах
        telegram_id = request.GET.get('id')
        telegram_hash = request.GET.get('hash')
        
        if telegram_id and telegram_hash:
            logger.info("🔐 Обнаружены данные от Telegram в URL параметрах главной страницы!")
            logger.info(f"  - ID: {telegram_id}, Hash: {telegram_hash}")
            logger.info(f"  - Referer: {request.META.get('HTTP_REFERER', 'N/A')}")
            logger.info(f"  - Все GET параметры: {dict(request.GET)}")
            
            # Перенаправляем на API endpoint с данными от Telegram
            # Собираем все параметры от Telegram
            telegram_params = {
                'id': telegram_id,
                'hash': telegram_hash,
            }
            # Добавляем остальные параметры от Telegram, если есть
            for param in ['auth_date', 'first_name', 'last_name', 'username', 'photo_url']:
                if request.GET.get(param):
                    telegram_params[param] = request.GET.get(param)
            
            # Формируем URL с параметрами
            from django.http import QueryDict
            from urllib.parse import urlencode
            auth_url = reverse('social_auth:telegram_auth_api')
            query_string = urlencode(telegram_params)
            redirect_url = f"{auth_url}?{query_string}"
            
            logger.info(f"  - Редирект на: {redirect_url}")
            return redirect(redirect_url)
        
        return super().dispatch(request, *args, **kwargs)

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
        # Получаем видео с учетом приоритета по order
        context['page_videos'] = PageVideo.objects.filter(page='index').order_by('order', 'title')
        # Получаем приоритетное видео для отображения
        context['page_video'] = PageVideo.get_priority_video('index')
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
        # Получаем видео с учетом приоритета по order
        context['page_videos'] = PageVideo.objects.filter(page='about').order_by('order', 'title')
        # Получаем приоритетное видео для отображения
        context['page_video'] = PageVideo.get_priority_video('about')
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
        
        # Определяем правильный URL для share
        current_url = self.request.build_absolute_uri()
        if '/share/' in current_url:
            # Если это share URL, используем его как есть
            share_url = current_url
        else:
            # Если это обычный URL, преобразуем в share URL
            share_url = current_url.replace('/post/', '/share/post/')
        
        # Исправляем canonical URL для использования основного домена
        host = self.request.get_host()
        scheme = 'https' if self.request.is_secure() else 'http'
        if host == 'mini.quiz-code.com':
            # Для mini app используем основной домен в canonical
            base_domain = 'quiz-code.com'
            canonical_url = current_url.replace(host, base_domain)
        else:
            canonical_url = current_url
        
        # Генерируем hreflang URLs для всех языков
        # ИСПРАВЛЕНИЕ: используем request.path как базовый путь и заменяем языковой префикс
        # reverse() уже добавляет языковой префикс, поэтому не добавляем его дважды
        from django.conf import settings
        current_lang = get_language()[:2]
        hreflang_en = None
        hreflang_ru = None
        
        # Получаем путь без языкового префикса (например, /post/slug/ из /en/post/slug/)
        current_path = self.request.path
        # Убираем языковой префикс если он есть
        path_without_lang = current_path
        for lang_code, _ in settings.LANGUAGES:
            lang_prefix = f"/{lang_code[:2]}/"
            if current_path.startswith(lang_prefix):
                path_without_lang = current_path[len(lang_prefix)-1:]  # -1 чтобы сохранить начальный /
                break
        
        if host == 'mini.quiz-code.com':
            base_domain = 'quiz-code.com'
        else:
            base_domain = host
        
        # Генерируем URL для каждого языка
        for lang_code, _ in settings.LANGUAGES:
            lang_prefix = lang_code[:2]
            lang_url = f"{scheme}://{base_domain}/{lang_prefix}{path_without_lang}"
            if lang_prefix == 'en':
                hreflang_en = lang_url
            elif lang_prefix == 'ru':
                hreflang_ru = lang_url
        
        # Мета-теги теперь обрабатываются в context_processors.py
        context['og_url'] = share_url
        context['canonical_url'] = canonical_url
        context['hreflang_en'] = hreflang_en
        context['hreflang_ru'] = hreflang_ru
        context['hreflang_x_default'] = hreflang_en or canonical_url
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
        
        # Определяем правильный URL для share
        current_url = self.request.build_absolute_uri()
        if '/share/' in current_url:
            # Если это share URL, используем его как есть
            share_url = current_url
        else:
            # Если это обычный URL, преобразуем в share URL
            share_url = current_url.replace('/project/', '/share/project/')
        
        # Исправляем canonical URL для использования основного домена
        host = self.request.get_host()
        scheme = 'https' if self.request.is_secure() else 'http'
        if host == 'mini.quiz-code.com':
            # Для mini app используем основной домен в canonical
            base_domain = 'quiz-code.com'
            canonical_url = current_url.replace(host, base_domain)
        else:
            canonical_url = current_url
        
        # Генерируем hreflang URLs для всех языков
        from django.conf import settings
        from django.urls import reverse
        current_lang = get_language()[:2]
        hreflang_en = None
        hreflang_ru = None
        
        for lang_code, _ in settings.LANGUAGES:
            lang_prefix = lang_code[:2]
            with translation.override(lang_code):
                try:
                    lang_url = reverse('blog:project_detail', kwargs={'slug': project.slug})
                    if host == 'mini.quiz-code.com':
                        base_domain = 'quiz-code.com'
                    else:
                        base_domain = host
                    full_lang_url = f"{scheme}://{base_domain}/{lang_prefix}{lang_url}"
                    if lang_prefix == 'en':
                        hreflang_en = full_lang_url
                    elif lang_prefix == 'ru':
                        hreflang_ru = full_lang_url
                except Exception:
                    continue
        
        # Мета-теги теперь обрабатываются в context_processors.py
        context['og_url'] = share_url
        context['canonical_url'] = canonical_url
        context['hreflang_en'] = hreflang_en
        context['hreflang_ru'] = hreflang_ru
        context['hreflang_x_default'] = hreflang_en or canonical_url
        context['related_projects'] = related_projects
        context['page_videos'] = PageVideo.objects.filter(page='project_detail')
        return context






class ResumeView(BreadcrumbsMixin, TemplateView):
    """
    Отображает страницу "Резюме".
    Загружает данные из БД (активное резюме) и передает в шаблон.
    """
    template_name = 'blog/resume.html'
    breadcrumbs = [
        {'name': _('Главная'), 'url': reverse_lazy('blog:home')},
        {'name': _('Резюме'), 'url': reverse_lazy('blog:resume')},
    ]

    def get_context_data(self, **kwargs):
        from .models import Resume
        context = super().get_context_data(**kwargs)
        context['is_admin'] = self.request.user.is_staff if self.request.user.is_authenticated else False
        context['meta_description'] = _('My professional resume with experience and skills.')
        context['meta_keywords'] = _('resume, programmer, portfolio')
        
        # Загружаем активное резюме из БД с prefetch related объектами
        resume = Resume.objects.filter(is_active=True).prefetch_related(
            'website_links',
            'skill_list',
            'work_history_items__responsibilities',
            'education_items',
            'language_skills'
        ).first()
        context['resume'] = resume
        
        # Если есть резюме, подготавливаем данные для удобного отображения
        if resume:
            # Преобразуем в формат для обратной совместимости с шаблоном
            context['websites'] = list(resume.website_links.order_by('order'))
            context['skills'] = list(resume.skill_list.order_by('order'))
            context['work_history'] = list(resume.work_history_items.order_by('order'))
            context['education'] = list(resume.education_items.order_by('order'))
            context['languages'] = list(resume.language_skills.order_by('order'))
        
        return context


def download_resume_pdf(request):
    """
    Генерирует и отдаёт PDF резюме на сервере через weasyprint.
    Без проблем с JavaScript и Shadow DOM.
    Использует template.render() с request=None для полного исключения контекстных процессоров.
    Это значительно уменьшает количество SQL запросов (с ~40 до ~5-8).
    """
    from django.http import HttpResponse
    from django.template.loader import get_template
    from django.conf import settings
    from weasyprint import HTML
    from .models import (
        Resume, ResumeWebsite, ResumeSkill, ResumeWorkHistory,
        ResumeResponsibility, ResumeEducation, ResumeLanguage
    )
    
    # Получаем язык из параметров или используем по умолчанию
    lang = request.GET.get('lang', 'en')
    
    # Загружаем резюме с полной оптимизацией запросов
    # Используем select_related и prefetch_related для минимизации запросов
    resume = Resume.objects.filter(is_active=True).prefetch_related(
        Prefetch('website_links', queryset=ResumeWebsite.objects.order_by('order')),
        Prefetch('skill_list', queryset=ResumeSkill.objects.order_by('order')),
        Prefetch(
            'work_history_items',
            queryset=ResumeWorkHistory.objects.order_by('order').prefetch_related(
                Prefetch('responsibilities', queryset=ResumeResponsibility.objects.order_by('order'))
            )
        ),
        Prefetch('education_items', queryset=ResumeEducation.objects.order_by('order')),
        Prefetch('language_skills', queryset=ResumeLanguage.objects.order_by('order'))
    ).first()
    
    if not resume:
        return HttpResponse('Резюме не найдено', status=404)
    
    # Принудительно загружаем все связанные данные заранее (evaluating querysets)
    # Это гарантирует, что все запросы выполняются здесь, а не в шаблоне
    websites = list(resume.website_links.order_by('order'))
    skills = list(resume.skill_list.order_by('order'))
    work_history = list(resume.work_history_items.order_by('order'))
    # Загружаем responsibilities для каждой записи истории работы
    for work_item in work_history:
        list(work_item.responsibilities.order_by('order'))  # Принудительная загрузка с сортировкой
    education = list(resume.education_items.order_by('order'))
    languages = list(resume.language_skills.order_by('order'))
    
    # Готовим минимальный контекст как словарь
    # Передаем request=None, чтобы template.render() не вызывал контекстные процессоры
    context_dict = {
        'resume': resume,
        'websites': websites,
        'skills': skills,
        'work_history': work_history,
        'education': education,
        'languages': languages,
        'current_lang': lang,
        'for_pdf': True,
        # Минимальные данные, которые могут понадобиться шаблону
        'STATIC_URL': settings.STATIC_URL,
        'MEDIA_URL': settings.MEDIA_URL,
    }
    
    # Загружаем шаблон и рендерим без контекстных процессоров (request=None)
    # Это полностью исключает вызов контекстных процессоров
    template = get_template('blog/resume_pdf.html')
    html_string = template.render(context_dict, request=None)
    
    # Генерируем PDF
    pdf_file = HTML(string=html_string).write_pdf()
    
    # Отдаём файл
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Resume_{lang.upper()}.pdf"'
    
    return response



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
        # Исправлено: фильтруем только опубликованные посты
        posts_list = Post.objects.filter(published=True)
        paginator = Paginator(posts_list, 5)
        page = self.request.GET.get('page')
        context['posts'] = paginator.get_page(page)
        # Исправлено: фильтруем только категории блога (не портфолио), чтобы JavaScript фильтр работал корректно
        context['categories'] = Category.objects.filter(is_portfolio=False)
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


class PrivacyPolicyView(BreadcrumbsMixin, TemplateView):
    """
    Отображает страницу "Политика конфиденциальности".
    Использует шаблон blog/privacy_policy.html.
    """
    template_name = 'blog/privacy_policy.html'
    breadcrumbs = [
        {'name': _('Главная'), 'url': reverse_lazy('blog:home')},
        {'name': _('Политика конфиденциальности'), 'url': reverse_lazy('blog:privacy_policy')},
    ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['meta_description'] = _('Privacy Policy - Learn how we collect, use, and protect your personal information.')
        context['meta_keywords'] = _('privacy policy, data protection, personal information, confidentiality')
        return context







@require_POST
def contact_form_submit(request):
    """
    Обрабатывает отправку формы обратной связи.

    Создаёт сообщение от системного пользователя 'Anonymous' вместо sender=None.
    """
    logger.info("Получен POST-запрос на /contact/submit/")
    logger.info(f"POST данные: {dict(request.POST)}")
    
    form = ContactForm(request.POST)

    if not form.is_valid():
        logger.warning(f"Невалидные данные в форме: {form.errors.as_json()}")
        # Возвращаем ошибки в формате JSON
        return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)

    logger.info("Форма прошла валидацию")
    cleaned_data = form.cleaned_data
    fullname = cleaned_data.get('fullname')
    email = cleaned_data.get('email')
    message_text = cleaned_data.get('message')
    logger.info(f"Обработка сообщения от {fullname} ({email})")

    try:
        # Проверяем настройки email
        logger.info(f"EMAIL_ADMIN настроен: {settings.EMAIL_ADMIN}")
        logger.info(f"DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")
        logger.info(f"EMAIL_HOST: {settings.EMAIL_HOST}")
        logger.info(f"EMAIL_PORT: {settings.EMAIL_PORT}")
        
        # Находим администратора
        admin_email = None
        if settings.EMAIL_ADMIN and len(settings.EMAIL_ADMIN) > 0:
            admin_email = settings.EMAIL_ADMIN[0]
        
        logger.info(f"Email администратора: {admin_email}")
        admin_user = None
        if admin_email:
            admin_user = CustomUser.objects.filter(email=admin_email).first()
            if not admin_user:
                logger.warning(f"Администратор с email {admin_email} не найден в базе")

        # Находим или создаём системного пользователя для анонимных сообщений
        logger.info("Поиск/создание системного пользователя Anonymous")
        anonymous_user, _ = CustomUser.objects.get_or_create(
            username='Anonymous',
            defaults={
                'email': 'anonymous@quizproject.com',
                'is_active': True,
                'is_staff': False
            }
        )
        logger.info(f"Системный пользователь найден/создан: {anonymous_user.username}")

        # Отправляем письмо (только если настроены email настройки)
        email_sent = False
        email_error_msg = None
        
        if settings.EMAIL_ADMIN and settings.DEFAULT_FROM_EMAIL:
            try:
                subject = f'Новое сообщение от {fullname} ({email})'
                message = f'Имя: {fullname}\nEmail: {email}\nСообщение:\n{message_text}'
                from_email = settings.DEFAULT_FROM_EMAIL
                recipient_list = settings.EMAIL_ADMIN

                logger.info(f"Отправка письма на {recipient_list} от {from_email}")
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=from_email,
                    recipient_list=recipient_list,
                    fail_silently=False,
                )
                email_sent = True
                logger.info(f"✅ Письмо успешно отправлено на {recipient_list}")
            except Exception as email_error:
                # Логируем ошибку с полным traceback
                import traceback
                email_error_msg = str(email_error)
                logger.error(f"❌ Ошибка отправки email: {email_error_msg}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                logger.error(f"Email настройки: HOST={settings.EMAIL_HOST}, PORT={settings.EMAIL_PORT}, FROM={settings.DEFAULT_FROM_EMAIL}, USER={settings.EMAIL_HOST_USER}")
        else:
            logger.warning("⚠️ Email настройки не заполнены. EMAIL_ADMIN или DEFAULT_FROM_EMAIL не установлены.")

        # Сохраняем сообщение в базе
        logger.info("Сохранение сообщения в базе данных")
        message_obj = Message.objects.create(
            sender=anonymous_user,  # Используем системного пользователя
            recipient=admin_user,
            content=message_text,
            fullname=fullname,
            email=email,
            is_read=False
        )
        logger.info(f"✅ Сообщение сохранено в базе (ID: {message_obj.id}) от {email} для {admin_user or 'No recipient'}")

        # Формируем ответ
        if email_sent:
            logger.info(f"✅ Сообщение успешно отправлено от {email}")
            return JsonResponse({'status': 'success', 'message': 'Сообщение отправлено'})
        elif email_error_msg:
            logger.warning(f"⚠️ Сообщение сохранено в БД, но письмо не отправлено: {email_error_msg}")
            return JsonResponse({'status': 'success', 'message': 'Сообщение сохранено, но письмо не отправлено'})
        else:
            logger.warning("⚠️ Сообщение сохранено в БД, но email настройки не заполнены")
            return JsonResponse({'status': 'success', 'message': 'Сообщение сохранено'})
            
    except Exception as e:
        import traceback
        logger.error(f"❌ Критическая ошибка отправки сообщения: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
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





def _build_safe_absolute_uri(request, url):
    """
    Безопасное построение абсолютного URI с обработкой ошибок.
    
    Args:
        request: Django request объект
        url: Относительный URL
        
    Returns:
        str: Абсолютный URI или пустая строка в случае ошибки
    """
    try:
        return request.build_absolute_uri(url)
    except Exception as e:
        logger.warning(f"Error building absolute URI for '{url}': {e}")
        return ''


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
    
    # Улучшенная логика поиска подтемы
    subtopic_queryset = Subtopic.objects.filter(topic=topic)

    # 1. Пробуем точное совпадение (игнорируя регистр)
    subtopic_obj = subtopic_queryset.filter(name__iexact=subtopic).first()

    # 2. Пробуем совпадение по slug (так же, как в шаблонах используется slugify)
    if not subtopic_obj:
        subtopics_list = list(subtopic_queryset)
        slug_matches = [item for item in subtopics_list if slugify(item.name) == subtopic]
        if slug_matches:
            if len(slug_matches) > 1:
                logger.warning(
                    "Multiple subtopics matched slug '%s' for topic '%s'. Using the first match (ID=%s)",
                    subtopic,
                    quiz_type,
                    slug_matches[0].id,
                )
            subtopic_obj = slug_matches[0]

    # 3. Пробуем более гибкий regex (например, generators-coroutines -> generators.*coroutines)
    if not subtopic_obj:
        normalized_subtopic = subtopic.replace('-', '.*')
        subtopic_query = Q(name__iregex=normalized_subtopic)
        logger.info(f"Searching subtopic: original={subtopic}, regex={normalized_subtopic}")
        fuzzy_matches = subtopic_queryset.filter(subtopic_query).order_by('id')
        match_count = fuzzy_matches.count()
        if match_count == 1:
            subtopic_obj = fuzzy_matches.first()
        elif match_count > 1:
            logger.warning(
                "Multiple subtopics matched regex '%s' for topic '%s'. Using the first match (ID=%s)",
                normalized_subtopic,
                quiz_type,
                fuzzy_matches.first().id if fuzzy_matches else 'unknown',
            )
            subtopic_obj = fuzzy_matches.first()

    if not subtopic_obj:
        logger.error("Subtopic '%s' not found for topic '%s'", subtopic, quiz_type)
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

    # Используем исходный параметр subtopic из URL для breadcrumbs, чтобы сохранить обратную совместимость
    # Параметр subtopic уже является валидным slug, который используется в URL
    # Это гарантирует, что breadcrumbs будут использовать тот же URL, что и текущая страница
    subtopic_slug_for_url = subtopic
    
    # Используем reverse вместо reverse_lazy, так как функция выполняется во время запроса
    try:
        breadcrumbs_list = [
            {'name': str(_('Home')), 'url': reverse('blog:home')},
            {'name': str(_('Quizzes')), 'url': reverse('blog:quizes')},
            {'name': topic.name, 'url': reverse('blog:quiz_detail', kwargs={'quiz_type': topic.name.lower()})},
            {'name': subtopic_obj.name, 'url': reverse('blog:quiz_difficulty', kwargs={'quiz_type': topic.name.lower(), 'subtopic': subtopic_slug_for_url})},
        ]
    except Exception as e:
        logger.error(f"Error building breadcrumbs for subtopic '{subtopic_obj.name}': {e}", exc_info=True)
        # Fallback: используем исходный параметр из URL
        breadcrumbs_list = [
            {'name': str(_('Home')), 'url': reverse('blog:home')},
            {'name': str(_('Quizzes')), 'url': reverse('blog:quizes')},
            {'name': topic.name, 'url': reverse('blog:quiz_detail', kwargs={'quiz_type': topic.name.lower()})},
            {'name': subtopic_obj.name, 'url': reverse('blog:quiz_difficulty', kwargs={'quiz_type': topic.name.lower(), 'subtopic': subtopic})},
        ]

    context = {
        'topic': topic,
        'subtopic': subtopic_obj,
        'difficulties': difficulties,
        'breadcrumbs': breadcrumbs_list,
        'breadcrumbs_json_ld': {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": index + 1,
                    "name": crumb['name'],
                    "item": _build_safe_absolute_uri(request, crumb['url']) if crumb.get('url') else ''
                }
                for index, crumb in enumerate(breadcrumbs_list)
                if crumb.get('url')  # Пропускаем элементы без URL
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
    
    # Улучшенная логика поиска подтемы (аналогично quiz_difficulty)
    subtopic_queryset = Subtopic.objects.filter(topic=topic)

    # 1. Пробуем точное совпадение (игнорируя регистр)
    subtopic_obj = subtopic_queryset.filter(name__iexact=subtopic).first()

    # 2. Пробуем совпадение по slug (так же, как в шаблонах используется slugify)
    if not subtopic_obj:
        subtopics_list = list(subtopic_queryset)
        slug_matches = [item for item in subtopics_list if slugify(item.name) == subtopic]
        if slug_matches:
            if len(slug_matches) > 1:
                logger.warning(
                    "Multiple subtopics matched slug '%s' for topic '%s'. Using the first match (ID=%s)",
                    subtopic,
                    quiz_type,
                    slug_matches[0].id,
                )
            subtopic_obj = slug_matches[0]

    # 3. Пробуем более гибкий regex (например, generators-coroutines -> generators.*coroutines)
    if not subtopic_obj:
        normalized_subtopic = subtopic.replace('-', '.*')
        subtopic_query = Q(name__iregex=normalized_subtopic)
        logger.info(f"Searching subtopic: original={subtopic}, regex={normalized_subtopic}")
        fuzzy_matches = subtopic_queryset.filter(subtopic_query).order_by('id')
        match_count = fuzzy_matches.count()
        if match_count == 1:
            subtopic_obj = fuzzy_matches.first()
        elif match_count > 1:
            logger.warning(
                "Multiple subtopics matched regex '%s' for topic '%s'. Using the first match (ID=%s)",
                normalized_subtopic,
                quiz_type,
                fuzzy_matches.first().id if fuzzy_matches else 'unknown',
            )
            subtopic_obj = fuzzy_matches.first()

    if not subtopic_obj:
        logger.error("Subtopic '%s' not found for topic '%s'", subtopic, quiz_type)
        raise Http404(f"Subtopic {subtopic} not found for topic {quiz_type}")
    
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

    try:
        topic = get_object_or_404(Topic, name__iexact=quiz_type)
        
        # Улучшенная логика поиска подтемы (аналогично quiz_subtopic)
        subtopic_queryset = Subtopic.objects.filter(topic=topic)

        # 1. Пробуем точное совпадение (игнорируя регистр)
        subtopic_obj = subtopic_queryset.filter(name__iexact=subtopic).first()

        # 2. Пробуем совпадение по slug (так же, как в шаблонах используется slugify)
        if not subtopic_obj:
            subtopics_list = list(subtopic_queryset)
            slug_matches = [item for item in subtopics_list if slugify(item.name) == subtopic]
            if slug_matches:
                if len(slug_matches) > 1:
                    logger.warning(
                        "Multiple subtopics matched slug '%s' for topic '%s'. Using the first match (ID=%s)",
                        subtopic,
                        quiz_type,
                        slug_matches[0].id,
                    )
                subtopic_obj = slug_matches[0]

        # 3. Пробуем более гибкий regex (например, generators-coroutines -> generators.*coroutines)
        if not subtopic_obj:
            normalized_subtopic = subtopic.replace('-', '.*')
            subtopic_query = Q(name__iregex=normalized_subtopic)
            logger.info(f"Searching subtopic: original={subtopic}, regex={normalized_subtopic}")
            fuzzy_matches = subtopic_queryset.filter(subtopic_query).order_by('id')
            match_count = fuzzy_matches.count()
            if match_count == 1:
                subtopic_obj = fuzzy_matches.first()
            elif match_count > 1:
                logger.warning(
                    "Multiple subtopics matched regex '%s' for topic '%s'. Using the first match (ID=%s)",
                    normalized_subtopic,
                    quiz_type,
                    fuzzy_matches.first().id if fuzzy_matches else 'unknown',
                )
                subtopic_obj = fuzzy_matches.first()

        if not subtopic_obj:
            logger.error("Subtopic '%s' not found for topic '%s'", subtopic, quiz_type)
            return JsonResponse({'error': f'Subtopic {subtopic} not found for topic {quiz_type}'}, status=404)
        
        task = get_object_or_404(Task, id=task_id, topic=topic, subtopic=subtopic_obj, published=True)
    except Http404 as e:
        logger.error(f"404 error in submit_task_answer: {e}")
        return JsonResponse({'error': 'Task or subtopic not found'}, status=404)
    except Exception as e:
        logger.error(f"Unexpected error in submit_task_answer: {e}", exc_info=True)
        return JsonResponse({'error': 'Internal server error'}, status=500)

    try:
        preferred_language = request.user.language if request.user.is_authenticated else 'en'
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

        # Обновляем статистику пользователя
        try:
            from django.db.models import Count, Q
            user_stats = TaskStatistics.objects.filter(user=request.user).aggregate(
                total_attempts=Count('id'),
                successful_attempts=Count('id', filter=Q(successful=True))
            )
            
            # Обновляем поля в модели пользователя
            request.user.quizzes_completed = user_stats['successful_attempts']
            request.user.average_score = round((user_stats['successful_attempts'] / user_stats['total_attempts'] * 100) if user_stats['total_attempts'] > 0 else 0, 1)
            request.user.total_points = request.user.calculate_rating()
            
            # Получаем любимую категорию
            favorite_topic = TaskStatistics.objects.filter(
                user=request.user,
                successful=True
            ).values('task__topic__name').annotate(count=Count('id')).order_by('-count').first()
            
            if favorite_topic:
                request.user.favorite_category = favorite_topic['task__topic__name']
            
            request.user.save(update_fields=['quizzes_completed', 'average_score', 'total_points', 'favorite_category'])
            
            # Очищаем кэш статистики
            request.user.invalidate_statistics_cache()
            
            logger.info(f"User stats updated: quizzes={request.user.quizzes_completed}, avg_score={request.user.average_score}%, points={request.user.total_points}")
        except Exception as e:
            logger.error(f"Error updating user statistics: {e}")

        logger.info(f"Answer submitted for task_id={task_id}, user={request.user}, is_correct={is_correct}")
        # Используем длинное объяснение для сайта, с fallback на короткое
        explanation = None
        if translation:
            explanation = translation.long_explanation or translation.explanation
        if not explanation:
            explanation = 'No explanation available.'
        
        return JsonResponse({
            'status': 'success',
            'is_correct': is_correct,
            'selected_answer': selected_answer,
            'results': results,
            'explanation': explanation
        })
    except Exception as e:
        logger.error(f"Unexpected error in submit_task_answer (after task lookup): {e}", exc_info=True)
        return JsonResponse({'error': 'Internal server error'}, status=500)


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

            # Отправляем уведомление получателю
            try:
                # Получаем telegram_id получателя из связанного профиля MiniAppUser
                from accounts.models import MiniAppUser
                from accounts.utils_folder.telegram_notifications import create_notification
                
                # Ищем MiniAppUser по связи с CustomUser
                recipient_mini_app = MiniAppUser.objects.filter(
                    linked_custom_user=recipient
                ).first()
                
                if recipient_mini_app:
                    notification_title = "✉️ Новое сообщение"
                    notification_message = f"{request.user.username} отправил вам сообщение:\n\n{content[:200]}"
                    
                    create_notification(
                        recipient_telegram_id=recipient_mini_app.telegram_id,
                        notification_type='message',
                        title=notification_title,
                        message=notification_message,
                        related_object_id=message.id,
                        related_object_type='message',
                        send_to_telegram=True
                    )
                    logger.info(f"📤 Уведомление о сообщении отправлено для {recipient_mini_app.telegram_id}")
                
            except Exception as e:
                logger.error(f"❌ Ошибка отправки уведомления о сообщении: {e}")

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
    
    Рендерит кастомную страницу 404 со статусом 404.
    Не использует редирект, чтобы избежать цепочек редиректов и проблем с SEO.
    """
    return render(request, '404.html', status=404)


def custom_413(request, exception=None):
    """
    Обрабатывает ошибку 413 (Request Entity Too Large).
    
    Отображает кастомную страницу с понятным объяснением ошибки.
    """
    return render(request, '413.html', status=413)






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
    if request.method == 'POST':
        form = TestimonialForm(request.POST)
        if form.is_valid():
            testimonial = form.save(commit=False)
            testimonial.user = request.user
            testimonial.save()
            messages.success(request, _('Спасибо за ваш отзыв! Он будет опубликован после проверки.'))
            return redirect(request.META.get('HTTP_REFERER', 'blog:home'))
        else:
            messages.error(request, _('Пожалуйста, исправьте ошибки в форме.'))
    return redirect('blog:home')




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
        form = TestimonialForm(request.POST)
        if form.is_valid():
            testimonial = form.save(commit=False)
            testimonial.user = request.user
            testimonial.save()
            return JsonResponse({'success': True, 'message': 'Отзыв успешно добавлен и ожидает модерации.'})
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)