import json
import os
import traceback

from django import forms
from django.conf import settings
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Max, Count
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import Category, Post, Project, PostImage, ProjectImage, Message, PageVideo, Testimonial, \
    MessageAttachment, MarqueeText, CustomURLValidator, PostLike, ProjectLike, PostShare, ProjectShare, \
    PostView, ProjectView, Resume, ResumeWebsite, ResumeSkill, ResumeWorkHistory, ResumeResponsibility, \
    ResumeEducation, ResumeLanguage
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
    filter_horizontal = ('telegram_channels',)
    actions = ['send_to_telegram_action']
    fieldsets = (
        (None, {
            'fields': ('title', 'slug', 'content', 'excerpt', 'category', 'video_url', 'published', 'featured',
                       'published_at')
        }),
        ('Telegram', {
            'fields': ('telegram_channels',),
            'description': 'Выберите каналы/группы для автоматической отправки поста при публикации'
        }),
        ('SEO', {
            'fields': ('meta_description', 'meta_keywords'),
            'classes': ('collapse',)
        }),
    )
    change_form_template = 'admin/blog/post_project_change_form.html'

    class Media:
        js = ('blog/js/admin_meta_validation.js',)
    
    def send_to_telegram_action(self, request, queryset):
        """
        Action для ручной отправки выбранных постов в Telegram каналы.
        """
        from platforms.services import send_telegram_post_sync
        from django.conf import settings
        from django.contrib.sites.models import Site
        from blog.utils import html_to_telegram_text, truncate_telegram_text
        
        success_count = 0
        error_count = 0
        
        for post in queryset:
            # Проверяем, есть ли выбранные каналы
            telegram_channels = post.telegram_channels.all()
            if not telegram_channels.exists():
                self.message_user(
                    request,
                    f'Пост "{post.title}" не имеет выбранных каналов для отправки.',
                    level='warning'
                )
                error_count += 1
                continue
            
            try:
                # Получаем URL поста
                post_url = post.get_absolute_url()
                if post_url:
                    try:
                        site = Site.objects.get_current()
                        full_url = f"https://{site.domain}{post_url}"
                    except:
                        full_url = f"{getattr(settings, 'PUBLIC_URL', 'https://quiz-code.com')}{post_url}"
                else:
                    full_url = None
                
                # Конвертируем HTML контент в формат Telegram
                telegram_text = html_to_telegram_text(post.content, post_url=full_url)
                
                # Обрезаем текст если нужно
                telegram_text = truncate_telegram_text(
                    telegram_text,
                    max_length=4096,
                    post_url=full_url,
                    is_caption=False
                )
                
                # Получаем медиафайлы поста
                main_image = post.get_main_image()
                photos_list = []
                gifs_list = []
                videos_list = []
                
                if main_image:
                    try:
                        if main_image.photo and main_image.photo.name:
                            # Используем сам файл - send_telegram_post_sync ожидает объект с методом chunks()
                            photos_list.append(main_image.photo)
                        elif main_image.gif and main_image.gif.name:
                            gifs_list.append(main_image.gif)
                        elif main_image.video and main_image.video.name:
                            videos_list.append(main_image.video)
                    except Exception as e:
                        logger.warning(f"Не удалось получить медиафайл для поста '{post.title}': {e}")
                
                # Отправляем в каждый выбранный канал
                # Ссылка на полную версию добавляется в текст через truncate_telegram_text
                post_success_count = 0
                for channel in telegram_channels:
                    try:
                        # Если есть медиа, используем caption (лимит 1024)
                        if photos_list or gifs_list or videos_list:
                            caption_text = truncate_telegram_text(
                                telegram_text,
                                max_length=1024,
                                post_url=full_url,
                                is_caption=True
                            )
                            success = send_telegram_post_sync(
                                channel=channel,
                                text=caption_text if caption_text else None,
                                photos=photos_list,
                                gifs=gifs_list,
                                videos=videos_list,
                                buttons=None  # Кнопки не используем, ссылка в тексте
                            )
                        else:
                            # Только текст
                            success = send_telegram_post_sync(
                                channel=channel,
                                text=telegram_text,
                                photos=None,
                                gifs=None,
                                videos=None,
                                buttons=None  # Кнопки не используем, ссылка в тексте
                            )
                        
                        if success:
                            post_success_count += 1
                    except Exception as e:
                        logger.error(f"Ошибка при отправке поста '{post.title}' в канал {channel.group_name}: {e}")
                
                if post_success_count > 0:
                    success_count += 1
                    self.message_user(
                        request,
                        f'Пост "{post.title}" отправлен в {post_success_count} из {telegram_channels.count()} каналов.',
                        level='success'
                    )
                else:
                    error_count += 1
                    self.message_user(
                        request,
                        f'Не удалось отправить пост "{post.title}" в выбранные каналы.',
                        level='error'
                    )
                    
            except Exception as e:
                error_count += 1
                logger.error(f"Ошибка при отправке поста '{post.title}' в Telegram: {e}")
                self.message_user(
                    request,
                    f'Ошибка при отправке поста "{post.title}": {str(e)}',
                    level='error'
                )
        
        if success_count > 0:
            self.message_user(
                request,
                f'Успешно отправлено {success_count} постов в Telegram.',
                level='success'
            )
    
    send_to_telegram_action.short_description = 'Отправить выбранные посты в Telegram'

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
        Улучшена обработка ошибок и логирование.
        """
        selected_items = request.POST.getlist('_selected_action')
        logger.info(f"Получены элементы для удаления: {selected_items}")
        if not selected_items:
            self.message_user(request, _("Не выбрано ни одного элемента для удаления."), level='warning')
            return

        actual_deleted_messages_count = 0
        successfully_deleted_message_pks = []

        for item_ids_str in selected_items:
            try:
                message_ids_list = [int(mid) for mid in item_ids_str.split(',') if mid]
                logger.info(f"Обработка ID сообщений для удаления: {message_ids_list}")

                messages_to_delete = Message.objects.filter(id__in=message_ids_list)

                if not messages_to_delete.exists():
                    logger.warning(f"Сообщения с ID: {message_ids_list} не найдены, пропуск.")
                    continue

                for message in messages_to_delete:
                    message_pk_for_log = message.pk  # Сохраняем PK для логирования
                    logger.info(f"Попытка удаления сообщения PK: {message_pk_for_log}")

                    try:
                        with transaction.atomic():  # Оборачиваем удаление сообщения и его вложений в транзакцию
                            # Сначала удаляем вложения
                            if hasattr(message, 'attachments'):
                                try:
                                    attachments = message.attachments.all()
                                    logger.info(
                                        f"Найдено {attachments.count()} вложений для сообщения PK {message_pk_for_log}")
                                    for attachment in attachments:
                                        attachment_pk_for_log_inner = attachment.pk  # Сохраняем PK вложения
                                        try:
                                            # Проверяем наличие файла и пути перед удалением
                                            if attachment.file and hasattr(attachment.file,
                                                                           'path') and attachment.file.path and os.path.exists(
                                                    attachment.file.path):
                                                logger.info(
                                                    f"Удаление файла: {attachment.file.path} для вложения PK {attachment_pk_for_log_inner}")
                                                os.remove(attachment.file.path)
                                            elif attachment.file:  # Если файл есть, но путь некорректен или файла нет
                                                logger.warning(
                                                    f"Физический файл для вложения PK {attachment_pk_for_log_inner} не найден или путь некорректен. URL файла: {getattr(attachment.file, 'url', 'N/A')}")
                                            else:  # Если у вложения вообще нет файла
                                                logger.warning(
                                                    f"С вложением PK {attachment_pk_for_log_inner} не связан файл.")
                                        except Exception as e:
                                            logger.error(
                                                f"Ошибка при удалении физического файла для вложения PK {attachment_pk_for_log_inner}: {str(e)}")
                                            # Можно решить, прерывать ли операцию. Пока логируем и продолжаем удалять запись из БД.

                                        # Удаляем запись вложения из БД
                                        try:
                                            attachment.delete()
                                            logger.info(
                                                f"Удалена запись вложения из БД PK {attachment_pk_for_log_inner}")
                                        except Exception as e:
                                            logger.error(
                                                f"Ошибка при удалении записи вложения из БД PK {attachment_pk_for_log_inner}: {str(e)}")
                                            raise  # Перебрасываем исключение, чтобы откатить транзакцию для этого сообщения
                                except Exception as e:
                                    logger.error(
                                        f"Ошибка при обработке вложений для сообщения PK {message_pk_for_log}: {str(e)}")
                                    raise  # Перебрасываем исключение, чтобы откатить транзакцию
                            else:
                                logger.info(f"Для сообщения PK {message_pk_for_log} нет связи 'attachments'.")

                            # Затем удаляем само сообщение
                            message.delete()
                            logger.info(f"Удалено сообщение PK {message_pk_for_log}")
                            actual_deleted_messages_count += 1
                            if message_pk_for_log not in successfully_deleted_message_pks:
                                successfully_deleted_message_pks.append(message_pk_for_log)

                    except Exception as e:  # Перехватываем ошибки из блока транзакции
                        logger.error(
                            f"Не удалось удалить сообщение PK {message_pk_for_log} и его вложения из-за ошибки: {str(e)}")
                        self.message_user(request,
                                          _(f"Ошибка при удалении сообщения PK {message_pk_for_log}: {str(e)}"),
                                          level='error')

            except ValueError:  # Ошибка преобразования ID сообщения в int
                logger.error(f"Обнаружен неверный формат ID в элементе: '{item_ids_str}'")
                self.message_user(request, _(f"Обнаружен неверный формат ID сообщения: '{item_ids_str}'."),
                                  level='error')
            except Exception as e:  # Другие общие ошибки при обработке item_ids_str
                logger.error(f"Общая ошибка при обработке элемента '{item_ids_str}' для удаления: {str(e)}")
                self.message_user(request, _(f"Ошибка при обработке элемента для удаления: {str(e)}"), level='error')

        if actual_deleted_messages_count > 0:
            deleted_pks_str = ', '.join(map(str, successfully_deleted_message_pks))
            self.message_user(request,
                              _(f"Успешно удалено {actual_deleted_messages_count} сообщений (ID: {deleted_pks_str}) и их вложений."))
        else:
            # Проверяем, были ли уже добавлены сообщения об ошибках
            # _loaded_messages может быть не доступен напрямую или быть внутренним API, используем messages.get_messages
            has_error_messages = any(msg.level == logging.ERROR for msg in admin.messages.get_messages(request))
            if not has_error_messages:  # Показываем это сообщение, только если не было специфических ошибок
                self.message_user(request, _("Сообщения для удаления не найдены или уже были удалены."),
                                  level='warning')

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
    list_display = ('title', 'page', 'media_type', 'get_show_media_display', 'get_show_text_display', 'order')
    list_filter = ('page', 'media_type', 'show_media', 'show_text')
    search_fields = ('title',)
    ordering = ('order', 'title')
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('page', 'title', 'order')
        }),
        ('Медиа контент (десктоп)', {
            'fields': ('media_type', 'video_url', 'video_file', 'gif'),
            'description': 'Видео для отображения на десктопных устройствах. Оставьте поле "Тип медиа" пустым (------), чтобы показывать только текст без видео.'
        }),
        ('Медиа контент (мобильная версия)', {
            'fields': ('mobile_media_type', 'mobile_video_url', 'mobile_video_file', 'mobile_gif'),
            'description': 'Видео для отображения на мобильных устройствах. Если не указано, будет использоваться основное видео.'
        }),
        ('Настройки отображения', {
            'fields': ('show_media', 'show_text', 'text_content'),
            'description': 'Выберите, что показывать на странице. Можно показывать медиа и текст вместе, либо по отдельности.'
        }),
    )
    
    def get_show_media_display(self, obj):
        """Отображает статус показа медиа."""
        from django.utils.safestring import mark_safe
        if obj.show_media:
            return mark_safe('<span style="color: #4CAF50; font-weight: bold;">✓ Медиа</span>')
        else:
            return mark_safe('<span style="color: #999;">✗ Медиа</span>')
    get_show_media_display.short_description = 'Медиа'
    
    def get_show_text_display(self, obj):
        """Отображает статус показа текста."""
        from django.utils.safestring import mark_safe
        if obj.show_text:
            return mark_safe('<span style="color: #4CAF50; font-weight: bold;">✓ Текст</span>')
        else:
            return mark_safe('<span style="color: #999;">✗ Текст</span>')
    get_show_text_display.short_description = 'Текст'
    
    class Media:
        js = ('blog/js/pagevideo_admin.js',)



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










class MarqueeTextForm(forms.ModelForm):
    """
    Форма для управления моделью MarqueeText с поддержкой многоязычных текстов.
    """

    class Meta:
        model = MarqueeText
        fields = [
            'is_active', 'link_url', 'link_target_blank', 'order',
            'text_en', 'text_ru', 'text_es', 'text_fr', 'text_de',
            'text_zh', 'text_ja', 'text_tj', 'text_tr', 'text_ar',
            'text'
        ]
        widgets = {
            'link_url': forms.TextInput(attrs={
                'placeholder': 'https://example.com или tg://resolve?domain@username',
                'style': 'width: 100%;'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.info("MarqueeTextForm init called")
        logger.info(f"Form fields: {list(self.fields.keys())}")

        # Добавляем дополнительную справку для поля URL
        if 'link_url' in self.fields:
            self.fields['link_url'].help_text = (
                "Поддерживаемые форматы:\n"
                "• HTTP/HTTPS: https://example.com\n"
                "• Telegram: tg://resolve?domain@username\n"
                "• Telegram: tg://resolve?domain=@username"
            )

    def clean_link_url(self):
        """
        Дополнительная валидация для поля link_url.
        """
        link_url = self.cleaned_data.get('link_url', '').strip()

        if not link_url:
            return link_url

        logger.info(f"Validating URL: {link_url}")

        try:
            # Используем валидатор из модели
            validator = CustomURLValidator()
            validator(link_url)
            logger.info(f"URL validation passed: {link_url}")
            return link_url

        except ValidationError as e:
            logger.error(f"URL validation failed for {link_url}: {e}")
            # Для отладки - попробуем более мягкую валидацию
            if link_url.startswith('tg://'):
                # Базовая проверка для Telegram URL
                if len(link_url) > 10 and ('resolve' in link_url or 'msg_url' in link_url or 'join' in link_url):
                    logger.info(f"Telegram URL passed basic validation: {link_url}")
                    return link_url

            raise ValidationError(f"Недопустимый URL: {str(e)}")

    def clean(self):
        """
        Общая валидация формы.
        """
        cleaned_data = super().clean()

        # Проверяем, что хотя бы один текст заполнен
        text_fields = ['text', 'text_en', 'text_ru', 'text_es', 'text_fr',
                       'text_de', 'text_zh', 'text_ja', 'text_tj', 'text_tr', 'text_ar']

        if not any(cleaned_data.get(field) for field in text_fields):
            raise ValidationError('Необходимо заполнить хотя бы одно текстовое поле')

        return cleaned_data

    def save(self, commit=True):
        """
        Сохраняет данные формы, обновляя text на основе text_en, если он заполнен.
        """
        instance = super().save(commit=False)

        # Если основной текст пуст, копируем из английского
        if not instance.text and instance.text_en:
            instance.text = instance.text_en

        if commit:
            instance.save()

        logger.info(f"Saved instance: text_en={instance.text_en}, text={instance.text}, "
                    f"link_url={instance.link_url}, order={instance.order}")
        return instance


@admin.register(MarqueeText)
class MarqueeTextAdmin(admin.ModelAdmin):
    """
    Админ-панель для модели MarqueeText.
    """
    form = MarqueeTextForm
    list_display = ("get_preview_text", "is_active", "has_link", "link_url", "order")
    search_fields = ('text', 'text_en', 'text_ru')
    list_filter = ('is_active',)
    ordering = ('order', 'text')

    fieldsets = [
        (None, {
            'fields': ['is_active', 'order'],
        }),
        ('Ссылка', {
            'fields': ['link_url', 'link_target_blank'],
            'description': 'Необязательная ссылка для текста бегущей строки'
        }),
        ('Основной текст', {
            'fields': ['text'],
            'description': 'Основной текст (используется как запасной вариант)'
        }),
        ('Переводы', {
            'fields': [
                'text_en', 'text_ru', 'text_es', 'text_fr', 'text_de',
                'text_zh', 'text_ja', 'text_tj', 'text_tr', 'text_ar'
            ],
            'description': 'Заполните текст на нужных языках. Текст на текущем языке будет выбран автоматически.',
            'classes': ['collapse']  # Сворачиваем секцию по умолчанию
        }),
    ]

    def get_form(self, request, obj=None, **kwargs):
        """
        Переопределяет метод get_form для логирования.
        """
        logger.info("MarqueeTextAdmin get_form called")
        form = super().get_form(request, obj, **kwargs)
        logger.info(f"Form fields: {list(form.base_fields.keys())}")
        return form

    def get_preview_text(self, obj):
        """
        Возвращает первые 50 символов текста для предпросмотра.
        """
        text = obj.get_text() or obj.text or "-"
        return text[:50] + "..." if len(text) > 50 else text

    get_preview_text.short_description = "Текст"

    def has_link(self, obj):
        """
        Показывает, есть ли ссылка у объекта.
        """
        return bool(obj.link_url)

    has_link.boolean = True
    has_link.short_description = "Ссылка?"

    def save_model(self, request, obj, form, change):
        """
        Дополнительная обработка при сохранении через админку.
        """
        logger.info(f"Admin save_model called for: {obj}")
        super().save_model(request, obj, form, change)


@admin.register(PostLike)
class PostLikeAdmin(admin.ModelAdmin):
    list_display = ('user', 'post', 'created_at')
    list_filter = ('created_at', 'post__category')
    search_fields = ('user__username', 'post__title')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'post')


@admin.register(ProjectLike)
class ProjectLikeAdmin(admin.ModelAdmin):
    list_display = ('user', 'project', 'created_at')
    list_filter = ('created_at', 'project__category')
    search_fields = ('user__username', 'project__title')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'project')


@admin.register(PostShare)
class PostShareAdmin(admin.ModelAdmin):
    list_display = ('user', 'post', 'platform', 'created_at')
    list_filter = ('platform', 'created_at', 'post__category')
    search_fields = ('user__username', 'post__title', 'shared_url')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'post')


@admin.register(ProjectShare)
class ProjectShareAdmin(admin.ModelAdmin):
    list_display = ('user', 'project', 'platform', 'created_at')
    list_filter = ('platform', 'created_at', 'project__category')
    search_fields = ('user__username', 'project__title', 'shared_url')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'project')


@admin.register(PostView)
class PostViewAdmin(admin.ModelAdmin):
    list_display = ('post', 'user', 'ip_address', 'created_at')
    list_filter = ('created_at', 'post__category')
    search_fields = ('post__title', 'user__username', 'ip_address')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'post')


@admin.register(ProjectView)
class ProjectViewAdmin(admin.ModelAdmin):
    list_display = ('project', 'user', 'ip_address', 'created_at')
    list_filter = ('created_at', 'project__category')
    search_fields = ('project__title', 'user__username', 'ip_address')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'project')


class ResumeWebsiteInline(admin.TabularInline):
    """Inline редактирование веб-сайтов"""
    model = ResumeWebsite
    extra = 1
    fields = ('url', 'order')
    verbose_name = "Веб-сайт"
    verbose_name_plural = "Веб-сайты"


class ResumeSkillInline(admin.TabularInline):
    """Inline редактирование навыков"""
    model = ResumeSkill
    extra = 1
    fields = ('name', 'order')
    verbose_name = "Навык"
    verbose_name_plural = "Навыки"


class ResumeResponsibilityInline(admin.TabularInline):
    """Inline редактирование обязанностей"""
    model = ResumeResponsibility
    extra = 1
    fields = ('text_en', 'text_ru', 'order')
    verbose_name = "Обязанность"
    verbose_name_plural = "Обязанности"


class ResumeWorkHistoryInline(admin.StackedInline):
    """Inline редактирование истории работы"""
    model = ResumeWorkHistory
    extra = 0
    fields = (
        ('title_en', 'title_ru'),
        ('period_en', 'period_ru'),
        ('company_en', 'company_ru'),
        'order'
    )
    verbose_name = "Запись истории работы"
    verbose_name_plural = "История работы"
    
    def get_formset(self, request, obj=None, **kwargs):
        """Добавляем inline для обязанностей внутри истории работы"""
        formset = super().get_formset(request, obj, **kwargs)
        return formset


class ResumeEducationForm(forms.ModelForm):
    """Форма, делающая поля образования необязательными."""

    class Meta:
        model = ResumeEducation
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        """Отмечаем все текстовые поля как необязательные."""
        super().__init__(*args, **kwargs)
        optional_fields = (
            'title_en',
            'title_ru',
            'period_en',
            'period_ru',
            'institution_en',
            'institution_ru',
        )
        for field_name in optional_fields:
            if field_name in self.fields:
                # Явно убираем required
                self.fields[field_name].required = False
                # Убираем атрибут required из виджета
                if 'required' in self.fields[field_name].widget.attrs:
                    del self.fields[field_name].widget.attrs['required']
    
    def clean(self):
        """Дополнительная валидация - разрешаем пустые поля."""
        cleaned_data = super().clean()
        # Все поля уже необязательные благодаря blank=True в модели
        # и required=False в форме, поэтому просто возвращаем данные
        return cleaned_data


class ResumeEducationInline(admin.StackedInline):
    """Inline редактирование образования"""
    model = ResumeEducation
    form = ResumeEducationForm
    extra = 0
    fields = (
        ('title_en', 'title_ru'),
        ('period_en', 'period_ru'),
        ('institution_en', 'institution_ru'),
        'order'
    )
    verbose_name = "Запись об образовании"
    verbose_name_plural = "Образование"


class ResumeLanguageInline(admin.TabularInline):
    """Inline редактирование языков"""
    model = ResumeLanguage
    extra = 1
    fields = ('name_en', 'name_ru', 'level', 'order')
    verbose_name = "Язык"
    verbose_name_plural = "Языки"


@admin.register(Resume)
class ResumeAdmin(admin.ModelAdmin):
    """
    Админ-панель для управления резюме.
    Удобное редактирование всех полей с inline-формами вместо JSON.
    """
    list_display = ('name', 'email', 'is_active', 'updated_at', 'created_at')
    list_filter = ('is_active', 'created_at', 'updated_at')
    search_fields = ('name', 'email', 'summary_en', 'summary_ru')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-is_active', '-updated_at')
    
    inlines = [
        ResumeWebsiteInline,
        ResumeSkillInline,
        ResumeWorkHistoryInline,
        ResumeEducationInline,
        ResumeLanguageInline,
    ]
    
    fieldsets = (
        ('✏️ Основная информация', {
            'fields': ('name', 'is_active'),
            'description': 'Имя и статус активности резюме'
        }),
        ('📞 Контактная информация', {
            'fields': (
                ('contact_info_en', 'contact_info_ru'),
                'email'
            ),
            'description': 'Контактные данные на двух языках'
        }),
        ('📝 Профессиональное резюме', {
            'fields': ('summary_en', 'summary_ru'),
            'description': 'Краткое описание профессиональных качеств'
        }),
        ('⚠️ Устаревшие JSON поля (не использовать)', {
            'fields': ('websites', 'skills', 'work_history', 'education', 'languages'),
            'classes': ('collapse',),
            'description': 'Эти поля оставлены для обратной совместимости. Используйте секции ниже для редактирования.'
        }),
        ('📅 Служебная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    class Media:
        css = {
            'all': ('admin/css/resume_admin.css',)
        }


@admin.register(ResumeWorkHistory)
class ResumeWorkHistoryAdmin(admin.ModelAdmin):
    """Админка для редактирования истории работы отдельно"""
    list_display = ('resume', 'title_en', 'period_en', 'company_en', 'order')
    list_filter = ('resume',)
    search_fields = ('title_en', 'title_ru', 'company_en', 'company_ru')
    ordering = ('resume', 'order')
    inlines = [ResumeResponsibilityInline]
    
    fieldsets = (
        ('Должность', {
            'fields': (('title_en', 'title_ru'),)
        }),
        ('Период работы', {
            'fields': (('period_en', 'period_ru'),)
        }),
        ('Компания', {
            'fields': (('company_en', 'company_ru'),)
        }),
        ('Порядок отображения', {
            'fields': ('resume', 'order')
        }),
    )



