# blog/admin.py
from django.contrib import admin
from .models import Category, Post, Project, PostImage, ProjectImage, Message, PageVideo


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_portfolio', 'created_at')
    list_filter = ('is_portfolio',)
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ('is_portfolio',)
    ordering = ('is_portfolio', 'name')


class PostImageInline(admin.TabularInline):
    model = PostImage
    extra = 1
    fields = ('photo', 'gif', 'video', 'is_main')
    verbose_name = "Медиа для поста"
    verbose_name_plural = "Медиа для поста"


class ProjectImageInline(admin.TabularInline):
    model = ProjectImage
    extra = 1
    fields = ('photo', 'gif', 'video', 'is_main')
    verbose_name = "Медиа для проекта"
    verbose_name_plural = "Медиа для проекта"


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    inlines = [PostImageInline]
    list_display = ('title', 'category', 'published', 'featured', 'created_at', 'views_count')
    list_filter = ('published', 'featured', 'category')
    search_fields = ('title', 'content', 'excerpt')
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    fields = ('title', 'slug', 'content', 'excerpt', 'category', 'video_url', 'published', 'featured', 'published_at')


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    inlines = [ProjectImageInline]
    list_display = ('title', 'category', 'featured', 'created_at')
    list_filter = ('featured', 'category')
    search_fields = ('title', 'description', 'technologies')
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    fields = ('title', 'slug', 'description', 'technologies', 'category', 'video_url', 'github_link', 'demo_link', 'featured')


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'recipient', 'created_at', 'is_read')
    list_filter = ('is_read',)
    search_fields = ('sender__username', 'recipient__username', 'content')


@admin.register(PageVideo)
class PageVideoAdmin(admin.ModelAdmin):
    """
    Админ-панель для управления видео на страницах 'index' и 'about'.

    Отображает список видео с фильтрацией по странице и возможностью сортировки.
    """
    list_display = ('title', 'page', 'video_url', 'video_file', 'gif', 'order')  # Добавили 'gif'
    list_filter = ('page',)
    search_fields = ('title',)
    ordering = ('order', 'title')
    fields = ('page', 'title', 'video_url', 'video_file', 'gif', 'order')  # Добавили 'gif'