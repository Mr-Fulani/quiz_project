# blog/admin.py
from django.contrib import admin
from .models import Category, Post, Project, PostImage, ProjectImage, Message, PageVideo, Testimonial


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
    list_display = ('fullname', 'email', 'sender', 'recipient', 'content_preview', 'created_at', 'is_read', 'is_deleted_by_sender', 'is_deleted_by_recipient')
    list_filter = ('is_read', 'created_at', 'is_deleted_by_sender', 'is_deleted_by_recipient')
    search_fields = ('fullname', 'email', 'content')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at',)
    actions = ['mark_as_read', 'mark_as_unread', 'soft_delete_for_sender', 'soft_delete_for_recipient']

    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Предпросмотр сообщения'

    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True)
        self.message_user(request, "Сообщения отмечены как прочитанные")
    mark_as_read.short_description = "Отметить как прочитанные"

    def mark_as_unread(self, request, queryset):
        queryset.update(is_read=False)
        self.message_user(request, "Сообщения отмечены как непрочитанные")
    mark_as_unread.short_description = "Отметить как непрочитанные"

    def soft_delete_for_sender(self, request, queryset):
        for message in queryset:
            message.soft_delete(message.sender)
        self.message_user(request, "Сообщения помечены как удалённые отправителем")
    soft_delete_for_sender.short_description = "Мягкое удаление для отправителя"

    def soft_delete_for_recipient(self, request, queryset):
        for message in queryset:
            message.soft_delete(message.recipient)
        self.message_user(request, "Сообщения помечены как удалённые получателем")
    soft_delete_for_recipient.short_description = "Мягкое удаление для получателя"




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


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ('user', 'text', 'created_at', 'is_approved')
    list_filter = ('is_approved', 'created_at')
    search_fields = ('user__username', 'text')
    actions = ['approve_testimonials', 'disapprove_testimonials']

    def approve_testimonials(self, request, queryset):
        queryset.update(is_approved=True)
    approve_testimonials.short_description = "Одобрить выбранные отзывы"

    def disapprove_testimonials(self, request, queryset):
        queryset.update(is_approved=False)
    disapprove_testimonials.short_description = "Отклонить выбранные отзывы"