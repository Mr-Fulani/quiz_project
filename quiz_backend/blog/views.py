from django.shortcuts import render
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from .models import Category, Post, Project
from .serializers import CategorySerializer, PostSerializer, ProjectSerializer
from rest_framework.views import APIView
from django.views.generic import TemplateView, DetailView
from django.core.paginator import Paginator
from django.contrib.auth.mixins import LoginRequiredMixin

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

class AboutView(TemplateView):
    template_name = 'blog/about.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['personal_info'] = {
            'name': 'Your Name',
            'title': 'Your Title',
            'email': 'your.email@example.com',
            'location': 'Your Location'
        }
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
