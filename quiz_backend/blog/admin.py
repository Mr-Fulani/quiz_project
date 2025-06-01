import os
import traceback

from django.contrib import admin
from django.db.models import Q, Max, Count
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

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
    Inline-форма для управления вложениями сообщений в админ-панели.
    Позволяет просматривать и удалять вложения через чекбоксы.
    """
    model = MessageAttachment
    fields = ('file', 'filename', 'uploaded_at', 'file_preview')
    readonly_fields = ('uploaded_at', 'file_preview')
    extra = 0
    can_delete = True  # Разрешаем удаление вложений # Изменено
    verbose_name = _("Вложение сообщения")
    verbose_name_plural = _("Вложения сообщения")

    def file_preview(self, obj):
        """
        Отображает превью для вложений: изображение для фото/GIF, ссылка для других файлов.

        Args:
            obj: Экземпляр MessageAttachment.

        Returns:
            str: HTML-код для превью или дефис, если файл отсутствует.
        """
        if not obj or not obj.file:
            logger.info(f"No file for attachment ID {obj.id}")
            return '-'
        try:
            file_ext = (obj.filename.lower().split('.')[-1] if obj.filename else '').strip()
            logger.info(f"Rendering preview for attachment ID {obj.id}, filename={obj.filename}, ext={file_ext}, url={obj.file.url}")
            if file_ext in ['jpg', 'jpeg', 'png', 'gif']:
                return format_html(
                    '<a href="{url}" target="_blank"><img src="{url}" class="attachment-preview" alt="{name}"/></a>',
                    url=obj.file.url, name=obj.filename or 'Image'
                )
            return format_html('<a href="{url}" target="_blank">{name}</a>', url=obj.file.url, name=obj.filename or 'File')
        except Exception as e:
            logger.error(f"Error rendering file preview for attachment {obj.id}: {str(e)}")
            return '-'

    def get_queryset(self, request):
        """
        Возвращает queryset вложений с логированием для отладки.

        Args:
            request: HTTP-запрос.

        Returns:
            QuerySet: Список вложений.
        """
        qs = super().get_queryset(request)
        logger.info(f"Fetching attachments for message, count: {qs.count()}")
        for obj in qs:
            logger.info(f"Attachment for message {obj.message_id}: ID={obj.id}, filename={obj.filename}, URL={obj.file.url}")
        return qs




@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    change_list_template = 'admin/blog/message/change_list.html'
    change_form_template = 'admin/blog/message/change_form.html'
    list_display = ('dialog_link', 'last_message', 'message_count', 'last_message_date')
    list_filter = ('is_read', 'created_at', 'sender', 'recipient')
    search_fields = ('sender__username', 'recipient__username', 'content', 'fullname', 'email')
    date_hierarchy = 'created_at'
    readonly_fields = ('id', 'created_at', 'dialog_link')
    fields = (
        'sender', 'recipient', 'content', 'fullname', 'email',
        'is_read', 'is_deleted_by_sender', 'is_deleted_by_recipient'
    )
    actions = ['mark_as_read', 'mark_as_unread', 'soft_delete_for_sender', 'soft_delete_for_recipient',
               'delete_selected_messages']
    inlines = [MessageAttachmentInline]
    list_per_page = 25
    list_select_related = True
    actions_on_top = True
    actions_on_bottom = False
    actions_selection_counter = True
    preserve_filters = True
    delete_confirmation_template = 'admin/blog/message/delete_confirmation.html'

    def delete_selected_messages(self, request, queryset):
        """
        Удаляет выбранные сообщения и их вложения.

        Args:
            request: HTTP-запрос.
            queryset: QuerySet выбранных сообщений.

        Returns:
            None: Сообщает пользователю об успешном удалении через message_user.
        """
        selected = request.POST.getlist('_selected_action')
        deleted_count = 0
        for message_ids in selected:
            try:
                message_ids_list = [int(mid) for mid in message_ids.split(',') if mid]
                messages = Message.objects.filter(id__in=message_ids_list)
                for message in messages:
                    for attachment in message.attachments.all():
                        if attachment.file and os.path.exists(attachment.file.path):
                            os.remove(attachment.file.path)
                            logger.info(f"Deleted file: {attachment.file.path}")
                        attachment.delete()
                    message.delete()
                    deleted_count += 1
            except Exception as e:
                logger.error(f"Error deleting messages with IDs {message_ids}: {str(e)}")
        self.message_user(request, _(f"Успешно удалено {deleted_count} сообщений и их вложений."))

    delete_selected_messages.short_description = _("Удалить выбранные сообщения")

    def mark_as_read(self, request, queryset):
        """
        Отмечает выбранные сообщения как прочитанные.

        Args:
            request: HTTP-запрос.
            queryset: QuerySet выбранных сообщений.

        Returns:
            None: Сообщает пользователю об успешном обновлении через message_user.
        """
        selected = request.POST.getlist('_selected_action')
        updated_count = 0
        for message_ids in selected:
            try:
                message_ids_list = [int(mid) for mid in message_ids.split(',') if mid]
                updated_count += Message.objects.filter(id__in=message_ids_list).update(is_read=True)
            except Exception as e:
                logger.error(f"Error marking messages as read with IDs {message_ids}: {str(e)}")
        self.message_user(request, _(f"Отмечено как прочитанные {updated_count} сообщений."))

    mark_as_read.short_description = _("Отметить как прочитанные")

    def mark_as_unread(self, request, queryset):
        """
        Отмечает выбранные сообщения как непрочитанные.

        Args:
            request: HTTP-запрос.
            queryset: QuerySet выбранных сообщений.

        Returns:
            None: Сообщает пользователю об успешном обновлении через message_user.
        """
        selected = request.POST.getlist('_selected_action')
        updated_count = 0
        for message_ids in selected:
            try:
                message_ids_list = [int(mid) for mid in message_ids.split(',') if mid]
                updated_count += Message.objects.filter(id__in=message_ids_list).update(is_read=False)
            except Exception as e:
                logger.error(f"Error marking messages as unread with IDs {message_ids}: {str(e)}")
        self.message_user(request, _(f"Отмечено как непрочитанные {updated_count} сообщений."))

    mark_as_unread.short_description = _("Отметить как непрочитанные")

    def soft_delete_for_sender(self, request, queryset):
        """
        Помечает сообщения как удалённые для отправителя.

        Args:
            request: HTTP-запрос.
            queryset: QuerySet выбранных сообщений.

        Returns:
            None: Сообщает пользователю об успешном обновлении через message_user.
        """
        selected = request.POST.getlist('_selected_action')
        updated_count = 0
        for message_ids in selected:
            try:
                message_ids_list = [int(mid) for mid in message_ids.split(',') if mid]
                updated_count += Message.objects.filter(id__in=message_ids_list).update(is_deleted_by_sender=True)
            except Exception as e:
                logger.error(f"Error soft deleting for sender with IDs {message_ids}: {str(e)}")
        self.message_user(request, _(f"Помечено как удалённое отправителем для {updated_count} сообщений."))

    soft_delete_for_sender.short_description = _("Поместить в корзину для отправителя")

    def soft_delete_for_recipient(self, request, queryset):
        """
        Помечает сообщения как удалённые для получателя.

        Args:
            request: HTTP-запрос.
            queryset: QuerySet выбранных сообщений.

        Returns:
            None: Сообщает пользователю об успешном обновлении через message_user.
        """
        selected = request.POST.getlist('_selected_action')
        updated_count = 0
        for message_ids in selected:
            try:
                message_ids_list = [int(mid) for mid in message_ids.split(',') if mid]
                updated_count += Message.objects.filter(id__in=message_ids_list).update(is_deleted_by_recipient=True)
            except Exception as e:
                logger.error(f"Error soft deleting for recipient with IDs {message_ids}: {str(e)}")
        self.message_user(request, _(f"Помечено как удалённое получателем для {updated_count} сообщений."))

    soft_delete_for_recipient.short_description = _("Поместить в корзину для получателя")

    def get_list_display(self, request):
        """
        Определяет поля для отображения в списке.

        Args:
            request: HTTP-запрос.

        Returns:
            list: Список полей для отображения.
        """
        if self._is_dialog_view(request):
            return ['content', 'sender', 'created_at', 'is_read']
        return ['dialog_link', 'last_message', 'message_count', 'last_message_date']

    def get_list_filter(self, request):
        """
        Определяет фильтры для списка.

        Args:
            request: HTTP-запрос.

        Returns:
            list: Список фильтров.
        """
        if self._is_dialog_view(request):
            return []
        return ['is_read', 'created_at', 'sender', 'recipient']

    def get_search_fields(self, request):
        """
        Определяет поля для поиска.

        Args:
            request: HTTP-запрос.

        Returns:
            list: Список полей для поиска.
        """
        if self._is_dialog_view(request):
            return []
        return ['sender__username', 'recipient__username', 'content', 'fullname', 'email']

    def get_date_hierarchy(self, request):
        """
        Определяет поле для иерархии дат.

        Args:
            request: HTTP-запрос.

        Returns:
            str or None: Поле для иерархии дат или None.
        """
        if self._is_dialog_view(request):
            return None
        return 'created_at'

    def get_actions(self, request):
        """
        Определяет доступные действия в зависимости от представления.

        Args:
            request: HTTP-запрос.

        Returns:
            dict: Словарь доступных действий.
        """
        actions = super().get_actions(request)
        if self._is_dialog_view(request):
            dialog_actions = {}
            if 'mark_as_read' in actions:
                dialog_actions['mark_as_read'] = actions['mark_as_read']
            if 'mark_as_unread' in actions:
                dialog_actions['mark_as_unread'] = actions['mark_as_unread']
            if 'delete_selected_messages' in actions:
                dialog_actions['delete_selected_messages'] = actions['delete_selected_messages']
            if 'soft_delete_for_sender' in actions:
                dialog_actions['soft_delete_for_sender'] = actions['soft_delete_for_sender']
            if 'soft_delete_for_recipient' in actions:
                dialog_actions['soft_delete_for_recipient'] = actions['soft_delete_for_recipient']
            return dialog_actions
        return actions

    def _is_dialog_view(self, request):
        """
        Проверяет, является ли текущее представление видом диалога.

        Args:
            request: HTTP-запрос.

        Returns:
            bool: True, если это вид диалога, иначе False.
        """
        dialog_param = request.GET.get('dialog', '').strip()
        return bool(dialog_param and '-' in dialog_param)

    def get_changelist(self, request, **kwargs):
        """
        Возвращает кастомный класс ChangeList для обработки списка.

        Args:
            request: HTTP-запрос.
            **kwargs: Дополнительные аргументы.

        Returns:
            CustomChangeList: Кастомный класс списка.
        """
        from django.contrib.admin.views.main import ChangeList

        class CustomChangeList(ChangeList):
            def get_filters_params(self, params=None):
                if params is None:
                    params = self.params.copy()
                params.pop('dialog', None)
                params.pop('read_filter', None)
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
                if 'dialog' in request.GET and '-' in request.GET.get('dialog', ''):
                    dialog_param = request.GET.get('dialog', '').strip()
                    read_filter = request.GET.get('read_filter', '').strip()

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

                        if not qs.filter(is_read=False).exists() and 'read_filter' not in request.GET:
                            qs.filter(is_read=False).update(is_read=True)

                        if read_filter == 'read':
                            qs = qs.filter(is_read=True)
                        elif read_filter == 'unread':
                            qs = qs.filter(is_read=False)

                        logger.info(
                            f"CustomChangeList: Filtered dialog: sender_id={sender_id}, recipient_id={recipient_id}, read_filter={read_filter}, messages={qs.count()}")
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
                preserved_params = ['dialog', 'read_filter']
                remove = [param for param in remove if param not in preserved_params]
                return super().get_query_string(new_params, remove)

        return CustomChangeList

    def get_dialogs(self, request, queryset):
        """
        Формирует список диалогов для отображения в админке.

        Args:
            request: HTTP-запрос.
            queryset: QuerySet сообщений.

        Returns:
            list: Список диалогов с метаданными, включая message_ids.
        """
        seen_pairs = set()
        dialogs = []
        for message in queryset.order_by('-created_at'):
            if not message.sender_id or not message.recipient_id:
                continue
            pair = tuple(sorted([message.sender_id, message.recipient_id]))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)

            dialog_messages = queryset.filter(
                Q(sender_id=message.sender_id, recipient_id=message.recipient_id) |
                Q(sender_id=message.recipient_id, recipient_id=message.sender_id)
            )
            last_message = dialog_messages.order_by('-created_at').first()
            is_read = not dialog_messages.filter(is_read=False).exists()  # Диалог считается прочитанным, если нет непрочитанных сообщений

            # Собираем ID всех сообщений в диалоге
            message_ids = list(dialog_messages.values_list('id', flat=True))

            dialog = {
                'sender_id': message.sender_id,
                'recipient_id': message.recipient_id,
                'sender_username': message.sender.username if message.sender else 'Аноним',
                'recipient_username': message.recipient.username if message.recipient else 'Аноним',
                'last_message': last_message.content[:50] + '...' if last_message and len(last_message.content) > 50 else last_message.content if last_message else '-',
                'message_count': dialog_messages.count(),
                'last_message_date': last_message.created_at if last_message else None,
                'is_read': is_read,
                'message_ids': message_ids  # Добавляем список ID сообщений
            }
            dialogs.append(dialog)
            logger.info(f"Dialog added: {dialog['sender_username']} ↔ {dialog['recipient_username']}, Messages: {dialog['message_count']}, Last message: {dialog['last_message']}, Message IDs: {dialog['message_ids']}")
        sorted_dialogs = sorted(dialogs, key=lambda x: x['last_message_date'] or '', reverse=True)
        logger.info(f"Total dialogs after sorting: {len(sorted_dialogs)}")
        return sorted_dialogs

    def changelist_view(self, request, extra_context=None):
        """
        Обрабатывает отображение списка сообщений или диалогов.

        Args:
            request: HTTP-запрос.
            extra_context: Дополнительный контекст для шаблона.

        Returns:
            HttpResponse: Ответ с отрендеренным списком.
        """
        logger.info(f"changelist_view called with URL: {request.get_full_path()}")
        logger.info(f"GET parameters: {dict(request.GET)}")
        logger.info(f"User: {request.user}, Is authenticated: True, Is superuser: {request.user.is_superuser}")

        extra_context = extra_context or {}
        is_dialog_view = self._is_dialog_view(request)
        extra_context['is_dialog_view'] = is_dialog_view

        logger.info(f"is_dialog_view: {is_dialog_view}")

        if not is_dialog_view:
            qs = self.get_queryset(request)
            extra_context['dialogs'] = self.get_dialogs(request, qs)
            logger.info(f"Dialogs count: {len(extra_context['dialogs']) if extra_context['dialogs'] else 0}")
            if extra_context['dialogs']:
                for dialog in extra_context['dialogs']:
                    logger.info(f"Passing dialog to template: {dialog['sender_username']} ↔ {dialog['recipient_username']}, Message IDs: {dialog['message_ids']}")
            else:
                logger.warning("No dialogs to pass to template")
        else:
            qs = self.get_queryset(request)
            logger.info(f"Dialog view queryset count: {qs.count()}")
            if not qs.exists():
                logger.warning("No messages found for dialog, redirecting to dialog list")
                self.message_user(request, "Сообщений для этого диалога не найдено.", level='warning')
                return HttpResponseRedirect(reverse('admin:blog_message_changelist'))

        response = super().changelist_view(request, extra_context=extra_context)
        logger.info(f"changelist_view response status: {getattr(response, 'status_code', 'Unknown')}")
        return response

    def get_paginator(self, request, queryset, per_page, orphans=0, allow_empty_first_page=True):
        """
        Настраивает пагинацию для списка сообщений.

        Args:
            request: HTTP-запрос.
            queryset: QuerySet сообщений.
            per_page: Количество элементов на странице.
            orphans: Минимальное количество элементов на последней странице.
            allow_empty_first_page: Разрешить пустую первую страницу.

        Returns:
            Paginator: Объект пагинации.
        """
        if 'dialog' in request.GET and '-' in request.GET.get('dialog', ''):
            logger.info("Dialog view detected - adjusting pagination")
            per_page = 100
        return super().get_paginator(request, queryset, per_page, orphans, allow_empty_first_page)

    def get_queryset(self, request):
        """
        Возвращает queryset сообщений с фильтрацией по диалогам.

        Args:
            request: HTTP-запрос.

        Returns:
            QuerySet: Список сообщений.
        """
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

    def dialog_link(self, obj):
        """
        Формирует ссылку на диалог между отправителем и получателем.

        Args:
            obj: Экземпляр Message.

        Returns:
            str: HTML-ссылка на диалог.
        """
        if hasattr(obj, 'sender') and obj.sender and obj.recipient:
            dialog_url = reverse('admin:blog_message_changelist') + f'?dialog={obj.sender.id}-{obj.recipient.id}'
            return format_html('<a href="{}">{}</a>', dialog_url, f"{obj.sender.username} ↔ {obj.recipient.username}")
        return '-'
    dialog_link.short_description = 'Диалог'

    def last_message(self, obj):
        """
        Возвращает сокращённый текст последнего сообщения.

        Args:
            obj: Экземпляр Message.

        Returns:
            str: Текст сообщения или дефис.
        """
        if hasattr(obj, 'content') and obj.content:
            return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
        return '-'
    last_message.short_description = 'Последнее сообщение'

    def message_count(self, obj):
        """
        Возвращает количество сообщений в диалоге (заглушка).

        Args:
            obj: Экземпляр Message.

        Returns:
            str: Дефис.
        """
        return '-'
    message_count.short_description = 'Сообщений'

    def last_message_date(self, obj):
        """
        Возвращает дату последнего сообщения.

        Args:
            obj: Экземпляр Message.

        Returns:
            datetime or str: Дата создания или дефис.
        """
        return obj.created_at if hasattr(obj, 'created_at') else '-'
    last_message_date.short_description = 'Дата'

    def change_view(self, request, object_id, form_url='', extra_context=None):
        """
        Обрабатывает отображение формы редактирования сообщения.

        Args:
            request: HTTP-запрос.
            object_id: ID сообщения.
            form_url: URL формы.
            extra_context: Дополнительный контекст.

        Returns:
            HttpResponse: Ответ с отрендеренной формой.
        """
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