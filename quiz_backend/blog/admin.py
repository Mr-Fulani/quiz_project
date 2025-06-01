import traceback

from django.contrib import admin
from django.db.models import Q, Max, Count
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html

from .models import Category, Post, Project, PostImage, ProjectImage, Message, PageVideo, Testimonial, MessageAttachment
import logging

logger = logging.getLogger(__name__)

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
    fieldsets = (
        (None, {
            'fields': ('title', 'slug', 'content', 'excerpt', 'category', 'video_url', 'published', 'featured',
                       'published_at')
        }),
        ('SEO', {
            'fields': ('meta_description', 'meta_keywords'),
            'classes': ('collapse',)
        }),
    )
    change_form_template = 'admin/blog/post_project_change_form.html'

    class Media:
        js = ('blog/js/admin_meta_validation.js',)

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    inlines = [ProjectImageInline]
    list_display = ('title', 'category', 'featured', 'created_at')
    list_filter = ('featured', 'category')
    search_fields = ('title', 'description', 'technologies')
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    fieldsets = (
        (None, {
            'fields': ('title', 'slug', 'description', 'technologies', 'category', 'video_url', 'github_link',
                       'demo_link', 'featured')
        }),
        ('SEO', {
            'fields': ('meta_description', 'meta_keywords'),
            'classes': ('collapse',)
        }),
    )
    change_form_template = 'admin/blog/post_project_change_form.html'

    class Media:
        js = ('blog/js/admin_meta_validation.js',)

class MessageAttachmentInline(admin.TabularInline):
    """
    Inline-форма для отображения вложений сообщений в админ-панели.
    """
    model = MessageAttachment
    fields = ('file', 'filename', 'uploaded_at', 'file_preview')
    readonly_fields = ('uploaded_at', 'file_preview')
    extra = 0
    can_delete = False
    verbose_name = "Вложение сообщения"
    verbose_name_plural = "Вложения сообщения"

    def file_preview(self, obj):
        """
        Превью файла: изображение для фото/GIF, ссылка для других файлов.
        """
        if not obj or not obj.file:
            logger.info(f"No file for attachment ID {obj.id}")
            return '-'
        try:
            file_ext = (obj.filename.lower().split('.')[-1] if obj.filename else '').strip()
            logger.info(
                f"Rendering preview for attachment ID {obj.id}, filename={obj.filename}, ext={file_ext}, url={obj.file.url}")
            if file_ext in ['jpg', 'jpeg', 'png', 'gif']:
                return format_html(
                    '<a href="{url}" target="_blank"><img src="{url}" class="attachment-preview" alt="{name}"/></a>',
                    url=obj.file.url, name=obj.filename or 'Image'
                )
            return format_html('<a href="{url}" target="_blank">{name}</a>', url=obj.file.url,
                               name=obj.filename or 'File')
        except Exception as e:
            logger.error(f"Error rendering file preview for attachment {obj.id}: {str(e)}")
            return '-'

    def get_queryset(self, request):
        """
        Логирование количества вложений для сообщения.
        """
        qs = super().get_queryset(request)
        logger.info(f"Fetching attachments for message, count: {qs.count()}")
        for obj in qs:
            logger.info(
                f"Attachment for message {obj.message_id}: ID={obj.id}, filename={obj.filename}, URL={obj.file.url}")
        return qs









@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """
    Админ-панель для модели Message с отображением диалогов.
    """
    change_list_template = 'admin/blog/message/change_list.html'
    change_form_template = 'admin/blog/message/change_form.html'
    list_display = ('dialog_link', 'last_message', 'message_count', 'last_message_date')
    list_filter = ('is_read', 'created_at', 'sender', 'recipient')
    search_fields = ('sender__username', 'recipient__username')
    date_hierarchy = 'created_at'
    readonly_fields = ('id', 'created_at', 'dialog_link')
    actions = ['mark_as_read', 'mark_as_unread', 'soft_delete_for_sender', 'soft_delete_for_recipient']
    inlines = [MessageAttachmentInline]
    list_per_page = 25

    def get_list_display(self, request):
        if 'dialog' in request.GET and '-' in request.GET.get('dialog', ''):
            return ['content', 'created_at', 'is_read']
        return super().get_list_display(request)

    def get_list_filter(self, request):
        if 'dialog' in request.GET and '-' in request.GET.get('dialog', ''):
            return []
        return super().get_list_filter(request)

    def get_search_fields(self, request):
        if 'dialog' in request.GET and '-' in request.GET.get('dialog', ''):
            return []
        return super().get_search_fields(request)

    def get_date_hierarchy(self, request):
        if 'dialog' in request.GET and '-' in request.GET.get('dialog', ''):
            return None
        return super().get_date_hierarchy(request)

    def get_changelist(self, request, **kwargs):
        from django.contrib.admin.views.main import ChangeList

        class CustomChangeList(ChangeList):
            def get_filters_params(self, params=None):
                if params is None:
                    params = self.params.copy()
                params.pop('dialog', None)
                return params

            def get_filters(self, request):
                if 'dialog' in request.GET and '-' in request.GET.get('dialog', ''):
                    return [], False
                return super().get_filters(request)

            def get_ordering(self, request, queryset):
                if 'dialog' in request.GET and '-' in request.GET.get('dialog', ''):
                    return ['created_at']
                return super().get_ordering(request, queryset)

            def get_queryset(self, request):
                # В диалоговом режиме игнорируем стандартную фильтрацию
                if 'dialog' in request.GET and '-' in request.GET.get('dialog', ''):
                    dialog_param = request.GET.get('dialog', '').strip()
                    try:
                        sender_id, recipient_id = map(int, dialog_param.split('-'))
                        if sender_id <= 0 or recipient_id <= 0:
                            logger.error(f"Invalid dialog parameter: '{dialog_param}' - IDs must be positive")
                            return self.model.objects.none()

                        qs = self.model.objects.filter(
                            (Q(sender_id=sender_id, recipient_id=recipient_id) |
                             Q(sender_id=recipient_id, recipient_id=sender_id)) &
                            Q(is_deleted_by_sender=False, is_deleted_by_recipient=False)
                        ).select_related('sender', 'recipient').order_by('created_at')

                        logger.info(f"CustomChangeList: Filtered dialog: sender_id={sender_id}, recipient_id={recipient_id}, messages={qs.count()}")
                        return qs
                    except (ValueError, TypeError) as e:
                        logger.error(f"Invalid dialog parameter: '{dialog_param}', error: {str(e)}")
                        return self.model.objects.none()
                return super().get_queryset(request)

            def get_query_string(self, new_params=None, remove=None):
                if remove is None:
                    remove = []
                elif isinstance(remove, dict):
                    remove = list(remove.keys())
                if 'dialog' not in remove:
                    remove = remove + ['dialog']
                return super().get_query_string(new_params, remove)

        return CustomChangeList

    def changelist_view(self, request, extra_context=None):
        logger.info(f"changelist_view called with URL: {request.get_full_path()}")
        logger.info(f"GET parameters: {dict(request.GET)}")
        logger.info(f"User: {request.user}, Is authenticated: {request.user.is_authenticated}, Is superuser: {request.user.is_superuser}")

        extra_context = extra_context or {}
        dialog_param = request.GET.get('dialog', '').strip()
        is_dialog_view = bool(dialog_param and '-' in dialog_param)
        extra_context['is_dialog_view'] = is_dialog_view

        logger.info(f"is_dialog_view: {is_dialog_view}")

        if not is_dialog_view:
            qs = self.get_queryset(request)
            extra_context['dialogs'] = self.get_dialogs(request, qs)
            logger.info(f"Dialogs count: {len(extra_context['dialogs']) if extra_context['dialogs'] else 0}")
        else:
            qs = self.get_queryset(request)
            logger.info(f"Dialog view queryset count: {qs.count()}")
            if not qs.exists():
                logger.warning("No messages found for dialog, redirecting to list view")
                self.message_user(request, "Сообщений для этого диалога не найдено.", level='warning')
                return HttpResponseRedirect(reverse('admin:blog_message_changelist'))

        response = super().changelist_view(request, extra_context=extra_context)
        logger.info(f"changelist_view response status: {getattr(response, 'status_code', 'Unknown')}")
        return response

    def get_paginator(self, request, queryset, per_page, orphans=0, allow_empty_first_page=True):
        if 'dialog' in request.GET and '-' in request.GET.get('dialog', ''):
            logger.info("Dialog view detected - adjusting pagination")
            per_page = 100
        return super().get_paginator(request, queryset, per_page, orphans, allow_empty_first_page)

    def get_queryset(self, request):
        stack = traceback.extract_stack()
        caller_info = f"{stack[-2].filename}:{stack[-2].lineno} in {stack[-2].name}"
        logger.info(f"get_queryset called from: {caller_info}")
        logger.info(f"Request URL: {request.get_full_path()}")

        qs = super().get_queryset(request).select_related('sender', 'recipient')

        if 'dialog' in request.GET:
            dialog_param = request.GET.get('dialog', '').strip()
            logger.info(f"Raw dialog parameter: '{dialog_param}'")

            if not dialog_param or '-' not in dialog_param:
                logger.info("Invalid or empty dialog parameter, returning base queryset")
                return qs.filter(is_deleted_by_sender=False, is_deleted_by_recipient=False)

            try:
                sender_id, recipient_id = map(int, dialog_param.split('-'))
                if sender_id <= 0 or recipient_id <= 0:
                    logger.error(f"Invalid dialog parameter: '{dialog_param}' - IDs must be positive")
                    return qs.none()

                qs = qs.filter(
                    (Q(sender_id=sender_id, recipient_id=recipient_id) |
                     Q(sender_id=recipient_id, recipient_id=sender_id)) &
                    Q(is_deleted_by_sender=False, is_deleted_by_recipient=False)
                ).order_by('created_at')

                logger.info(f"Filtered dialog: sender_id={sender_id}, recipient_id={recipient_id}, messages={qs.count()}")
                for msg in qs:
                    logger.info(f"Message ID={msg.id}, sender={msg.sender_id or 'None'}, recipient={msg.recipient_id or 'None'}, content={msg.content[:50]}")
                return qs

            except (ValueError, TypeError) as e:
                logger.error(f"Invalid dialog parameter: '{dialog_param}', error: {str(e)}")
                return qs.none()

        logger.info("No dialog parameter, returning all messages")
        return qs.filter(is_deleted_by_sender=False, is_deleted_by_recipient=False)

    def get_dialogs(self, request, qs):
        messages = qs.order_by('-created_at')
        dialogs = []
        seen_pairs = set()

        for message in messages:
            if not message.sender_id or not message.recipient_id:
                continue

            pair = tuple(sorted([message.sender_id, message.recipient_id]))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)

            dialog_messages = qs.filter(
                Q(sender_id=message.sender_id, recipient_id=message.recipient_id) |
                Q(sender_id=message.recipient_id, recipient_id=message.sender_id)
            )
            last_message = dialog_messages.order_by('-created_at').first()

            dialog = {
                'sender_id': message.sender_id,
                'recipient_id': message.recipient_id,
                'sender_username': message.sender.username if message.sender else 'Аноним',
                'recipient_username': message.recipient.username if message.recipient else 'Аноним',
                'last_message': last_message.content[:50] + '...' if last_message and len(last_message.content) > 50 else last_message.content if last_message else '-',
                'message_count': dialog_messages.count(),
                'last_message_date': last_message.created_at if last_message else None,
            }
            dialogs.append(dialog)

        return sorted(dialogs, key=lambda x: x['last_message_date'] or '', reverse=True)

    def dialog_link(self, obj):
        if hasattr(obj, 'sender') and obj.sender and obj.recipient:
            dialog_url = reverse('admin:blog_message_changelist') + f'?dialog={obj.sender.id}-{obj.recipient.id}'
            return format_html('<a href="{}">{}</a>', dialog_url, f"{obj.sender.username} ↔ {obj.recipient.username}")
        return '-'

    dialog_link.short_description = 'Диалог'

    def last_message(self, obj):
        if hasattr(obj, 'content') and obj.content:
            return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
        return '-'

    last_message.short_description = 'Последнее сообщение'

    def message_count(self, obj):
        return '-'

    message_count.short_description = 'Сообщений'

    def last_message_date(self, obj):
        return obj.created_at if hasattr(obj, 'created_at') else '-'

    last_message_date.short_description = 'Дата'

    def mark_as_read(self, request, queryset):
        Message.objects.filter(id__in=[obj.id for obj in queryset]).update(is_read=True)
        self.message_user(request, "Сообщения отмечены как прочитанные")

    mark_as_read.short_description = "Отметить как прочитанные"

    def mark_as_unread(self, request, queryset):
        Message.objects.filter(id__in=[obj.id for obj in queryset]).update(is_read=False)
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

    def change_view(self, request, object_id, form_url='', extra_context=None):
        logger.info(f"Rendering change view for message ID {object_id}")
        return super().change_view(request, object_id, form_url, extra_context)





@admin.register(PageVideo)
class PageVideoAdmin(admin.ModelAdmin):
    list_display = ('title', 'page', 'video_url', 'video_file', 'gif', 'order')
    list_filter = ('page',)
    search_fields = ('title',)
    ordering = ('order', 'title')
    fields = ('page', 'title', 'video_url', 'video_file', 'gif', 'order')

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