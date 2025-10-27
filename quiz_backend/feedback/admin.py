from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.contrib import messages
from django.http import HttpResponseRedirect
from django import forms
from .models import FeedbackMessage, FeedbackReply, FeedbackImage, FeedbackReplyImage
from .services import send_feedback_reply_to_telegram


class FeedbackReplyAdminForm(forms.ModelForm):
    """
    Кастомная форма для FeedbackReply с возможностью загрузки изображения
    """
    attach_image = forms.ImageField(
        required=False,
        label='Прикрепить изображение к ответу',
        help_text='Одно изображение (макс. 5MB, форматы: JPEG, PNG, GIF, WebP)',
        widget=forms.ClearableFileInput(attrs={'accept': 'image/*'})
    )
    
    class Meta:
        model = FeedbackReply
        fields = '__all__'
    
    def save(self, commit=True):
        """Сохраняем ответ и прикрепленное изображение"""
        instance = super().save(commit=commit)
        
        if commit and self.cleaned_data.get('attach_image'):
            # Создаем запись изображения
            FeedbackReplyImage.objects.create(
                reply=instance,
                image=self.cleaned_data['attach_image']
            )
        
        return instance


class FeedbackImageInline(admin.TabularInline):
    """
    Inline для отображения изображений к сообщению обратной связи
    """
    model = FeedbackImage
    extra = 0
    readonly_fields = ('image_preview', 'file_size_display', 'created_at')
    fields = ('image_preview', 'image', 'file_size_display', 'created_at')
    
    def image_preview(self, obj):
        """Превью изображения"""
        if obj.image:
            return format_html(
                '<a href="{}" target="_blank"><img src="{}" style="max-height: 100px; max-width: 200px; border: 1px solid #ddd; border-radius: 4px;"/></a>',
                obj.image.url,
                obj.image.url
            )
        return "Нет изображения"
    image_preview.short_description = 'Превью'
    
    def file_size_display(self, obj):
        """Отображение размера файла"""
        if obj.file_size:
            size_mb = obj.file_size_mb
            color = '#dc3545' if size_mb > 5 else '#28a745' if size_mb < 2 else '#ffc107'
            return format_html(
                '<span style="color: {}; font-weight: bold;">{} MB</span>',
                color,
                size_mb
            )
        return "—"
    file_size_display.short_description = 'Размер'


class FeedbackReplyImageInline(admin.TabularInline):
    """
    Inline для отображения изображений к ответу админа
    """
    model = FeedbackReplyImage
    extra = 0
    readonly_fields = ('image_preview', 'file_size_display', 'created_at')
    fields = ('image_preview', 'image', 'file_size_display', 'created_at')
    
    def image_preview(self, obj):
        """Превью изображения"""
        if obj.image:
            return format_html(
                '<a href="{}" target="_blank"><img src="{}" style="max-height: 100px; max-width: 200px; border: 1px solid #ddd; border-radius: 4px;"/></a>',
                obj.image.url,
                obj.image.url
            )
        return "Нет изображения"
    image_preview.short_description = 'Превью'
    
    def file_size_display(self, obj):
        """Отображение размера файла"""
        if obj.file_size:
            size_mb = obj.file_size_mb
            color = '#dc3545' if size_mb > 5 else '#28a745' if size_mb < 2 else '#ffc107'
            return format_html(
                '<span style="color: {}; font-weight: bold;">{} MB</span>',
                color,
                size_mb
            )
        return "—"
    file_size_display.short_description = 'Размер'


class FeedbackReplyInline(admin.StackedInline):
    """
    Inline для отображения ответов на сообщения поддержки
    """
    model = FeedbackReply
    form = FeedbackReplyAdminForm
    extra = 1  # Показываем одну пустую форму для добавления
    readonly_fields = ('admin', 'admin_telegram_id', 'admin_username', 'created_at', 'is_sent_to_user', 'sent_at', 'send_error', 'send_reply_button', 'images_count_display', 'attached_images_preview')
    fields = ('reply_text', 'attach_image', 'attached_images_preview', 'images_count_display', 'send_reply_button', 'admin', 'admin_telegram_id', 'admin_username', 'created_at', 'is_sent_to_user', 'sent_at', 'send_error')
    inlines = []  # Изображения ответов будут редактироваться отдельно
    
    def has_delete_permission(self, request, obj=None):
        return False  # Запрещаем удаление ответов
    
    def attached_images_preview(self, obj):
        """Превью уже прикрепленных изображений"""
        if obj and obj.id:
            images = obj.images.all()
            if images:
                html = '<div style="display: flex; gap: 10px; flex-wrap: wrap; margin-top: 10px;">'
                for img in images:
                    html += format_html(
                        '<div style="text-align: center;">'
                        '<a href="{}" target="_blank">'
                        '<img src="{}" style="max-height: 80px; max-width: 100px; border: 1px solid #ddd; border-radius: 4px;"/>'
                        '</a>'
                        '<div style="font-size: 10px; color: #666;">📦 {} MB</div>'
                        '</div>',
                        img.image.url,
                        img.image.url,
                        img.file_size_mb
                    )
                html += '</div>'
                return mark_safe(html)
            return "—"
        return "Сохраните ответ, чтобы прикрепить изображения"
    attached_images_preview.short_description = 'Прикрепленные изображения'
    
    def images_count_display(self, obj):
        """Отображение количества изображений"""
        if obj and obj.id:
            count = obj.images_count
            if count > 0:
                return format_html(
                    '<span style="color: #28a745; font-weight: bold;">📷 {} изобр.</span>',
                    count
                )
            return "Нет изображений"
        return "—"
    images_count_display.short_description = 'Изображения'

    def send_reply_button(self, obj):
        """Кнопка для отправки ответа"""
        if obj and obj.id:
            if not obj.is_sent_to_user:
                url = reverse('admin:feedback_feedbackreply_send', args=[obj.id])
                return format_html('<a href="{}" class="button" style="background: #28a745; color: white; padding: 5px 10px; text-decoration: none; border-radius: 3px;">📤 Отправить</a>', url)
            else:
                return format_html('<span style="color: green; font-weight: bold;">✅ Отправлено</span>')
        return "Сохраните ответ для отправки"
    send_reply_button.short_description = 'Действие'


@admin.register(FeedbackMessage)
class FeedbackMessageAdmin(admin.ModelAdmin):
    """
    Админка для управления сообщениями обратной связи
    """
    list_display = ('id', 'user_id', 'username', 'short_message', 'source', 'category', 'images_count_display', 'created_at', 'is_processed', 'replies_count', 'status_display')
    list_filter = ('is_processed', 'source', 'category', 'created_at')
    search_fields = ('user_id', 'username', 'message')
    readonly_fields = ('created_at', 'replies_count', 'last_reply_info', 'send_all_replies_button', 'images_preview')
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    inlines = [FeedbackImageInline, FeedbackReplyInline]
    
    def images_count_display(self, obj):
        """Отображение количества изображений в списке"""
        count = obj.images_count
        if count > 0:
            return format_html('<span style="color: #28a745;">📷 {}</span>', count)
        return "—"
    images_count_display.short_description = '📷'
    
    def images_preview(self, obj):
        """Превью всех изображений"""
        images = obj.images.all()
        if images:
            html = '<div style="display: flex; flex-wrap: wrap; gap: 10px;">'
            for img in images:
                html += format_html(
                    '<div style="text-align: center;">'
                    '<a href="{}" target="_blank">'
                    '<img src="{}" style="max-height: 150px; max-width: 200px; border: 2px solid #ddd; border-radius: 8px;"/>'
                    '</a>'
                    '<div style="font-size: 11px; color: #666; margin-top: 5px;">📦 {} MB</div>'
                    '</div>',
                    img.image.url,
                    img.image.url,
                    img.file_size_mb
                )
            html += '</div>'
            return mark_safe(html)
        return "Нет изображений"
    images_preview.short_description = 'Прикрепленные изображения'

    def save_formset(self, request, form, formset, change):
        """Автоматически заполняем поле admin при сохранении ответа и отмечаем сообщение как обработанное"""
        instances = formset.save(commit=False)
        for instance in instances:
            if isinstance(instance, FeedbackReply) and not instance.admin_id:
                instance.admin = request.user
                # Заполняем Telegram данные администратора
                instance.admin_telegram_id = getattr(request.user, 'telegram_id', None)
                instance.admin_username = getattr(request.user, 'username', None)
                # Отмечаем сообщение как обработанное
                if instance.feedback and not instance.feedback.is_processed:
                    instance.feedback.is_processed = True
                    instance.feedback.save(update_fields=['is_processed'])
        formset.save()
        super().save_formset(request, form, formset, change)

    def short_message(self, obj):
        """Сокращенная версия сообщения для отображения в списке"""
        return (obj.message[:50] + '...') if len(obj.message) > 50 else obj.message
    short_message.short_description = 'Сообщение'

    def replies_count(self, obj):
        """Количество ответов на сообщение"""
        return obj.replies_count
    replies_count.short_description = 'Ответов'

    def status_display(self, obj):
        """Отображение статуса сообщения"""
        if obj.replies_count > 0:
            # Проверяем есть ли отправленные ответы
            sent_replies = obj.feedbackreply_set.filter(is_sent_to_user=True).count()
            if sent_replies > 0:
                return format_html('<span style="color: green;">✓ Отвечено и отправлено</span>')
            else:
                return format_html('<span style="color: orange;">⚠ Отвечено (ожидает отправки)</span>')
        elif obj.is_processed:
            return format_html('<span style="color: orange;">⚠ Обработано без ответного сообщения от администратора</span>')
        else:
            return format_html('<span style="color: red;">● Новое</span>')
    status_display.short_description = 'Статус'

    def last_reply_info(self, obj):
        """Информация о последнем ответе"""
        last_reply = obj.last_reply
        if last_reply:
            status = "✅ Отправлено" if last_reply.is_sent_to_user else "⏳ Ожидает отправки"
            admin_name = last_reply.admin_username or (last_reply.admin.username if last_reply.admin else 'Неизвестно')
            return format_html(
                '<div><strong>Последний ответ:</strong> {}</div>'
                '<div><strong>От:</strong> {}</div>'
                '<div><strong>Статус:</strong> {}</div>',
                last_reply.short_reply,
                admin_name,
                status
            )
        return "Нет ответов"
    last_reply_info.short_description = 'Последний ответ'

    actions = ['mark_as_processed', 'mark_as_unprocessed', 'send_pending_replies']

    def mark_as_processed(self, request, queryset):
        """Отметить выбранные сообщения как обработанные"""
        queryset.update(is_processed=True)
    mark_as_processed.short_description = 'Отметить как обработанные'

    def mark_as_unprocessed(self, request, queryset):
        """Отметить выбранные сообщения как необработанные"""
        queryset.update(is_processed=False)
    mark_as_unprocessed.short_description = 'Отметить как необработанные'

    def send_pending_replies(self, request, queryset):
        """Отправить все ожидающие ответы"""
        sent_count = 0
        error_count = 0
        
        for feedback in queryset:
            pending_replies = feedback.feedbackreply_set.filter(is_sent_to_user=False)
            for reply in pending_replies:
                if send_feedback_reply_to_telegram(reply.id):
                    sent_count += 1
                else:
                    error_count += 1
        
        if sent_count > 0:
            messages.success(request, f"Успешно отправлено {sent_count} ответов")
        if error_count > 0:
            messages.error(request, f"Ошибка отправки {error_count} ответов")
            
    send_pending_replies.short_description = 'Отправить ожидающие ответы'

    def send_all_replies_action(self, request, feedback_id):
        """Действие для отправки всех ответов на сообщение"""
        try:
            feedback = FeedbackMessage.objects.get(id=feedback_id)
            pending_replies = feedback.feedbackreply_set.filter(is_sent_to_user=False)
            
            sent_count = 0
            error_count = 0
            
            for reply in pending_replies:
                if send_feedback_reply_to_telegram(reply.id):
                    sent_count += 1
                else:
                    error_count += 1
            
            if sent_count > 0:
                messages.success(request, f"Успешно отправлено {sent_count} ответов")
            if error_count > 0:
                messages.error(request, f"Ошибка отправки {error_count} ответов")
            if sent_count == 0 and error_count == 0:
                messages.warning(request, "Нет ответов для отправки")
                
        except FeedbackMessage.DoesNotExist:
            messages.error(request, "Сообщение не найдено")
        except Exception as e:
            messages.error(request, f"Ошибка: {str(e)}")
        
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/admin/'))

    def get_urls(self):
        """Добавляем кастомные URL для действий"""
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:feedback_id>/send-all-replies/',
                self.admin_site.admin_view(self.send_all_replies_action),
                name='feedback_feedbackmessage_send_all_replies',
            ),
        ]
        return custom_urls + urls

    def send_all_replies_button(self, obj):
        """Кнопка для отправки всех ответов на сообщение"""
        pending_count = obj.feedbackreply_set.filter(is_sent_to_user=False).count()
        if pending_count > 0:
            url = reverse('admin:feedback_feedbackmessage_send_all_replies', args=[obj.id])
            return format_html(
                '<a href="{}" class="button" style="background: #007cba; color: white; padding: 5px 10px; text-decoration: none; border-radius: 3px;">📤 Отправить все ({})</a>',
                url, pending_count
            )
        else:
            return format_html('<span style="color: gray;">Нет ответов для отправки</span>')
    send_all_replies_button.short_description = 'Отправить ответы'


@admin.register(FeedbackImage)
class FeedbackImageAdmin(admin.ModelAdmin):
    """
    Админка для управления изображениями к обратной связи
    """
    list_display = ('id', 'feedback_link', 'image_thumbnail', 'file_size_display', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('feedback__user_id', 'feedback__username', 'feedback__message')
    readonly_fields = ('image_large_preview', 'file_size_display', 'created_at')
    ordering = ('-created_at',)
    
    def feedback_link(self, obj):
        """Ссылка на сообщение"""
        url = reverse('admin:feedback_feedbackmessage_change', args=[obj.feedback.id])
        return format_html('<a href="{}">Сообщение #{}</a>', url, obj.feedback.id)
    feedback_link.short_description = 'Сообщение'
    
    def image_thumbnail(self, obj):
        """Миниатюра изображения"""
        if obj.image:
            return format_html(
                '<a href="{}" target="_blank"><img src="{}" style="max-height: 50px; max-width: 100px;"/></a>',
                obj.image.url,
                obj.image.url
            )
        return "—"
    image_thumbnail.short_description = 'Превью'
    
    def image_large_preview(self, obj):
        """Большое превью изображения"""
        if obj.image:
            return format_html(
                '<a href="{}" target="_blank"><img src="{}" style="max-width: 600px; border: 2px solid #ddd; border-radius: 8px;"/></a>',
                obj.image.url,
                obj.image.url
            )
        return "Нет изображения"
    image_large_preview.short_description = 'Изображение'
    
    def file_size_display(self, obj):
        """Отображение размера файла"""
        if obj.file_size:
            size_mb = obj.file_size_mb
            color = '#dc3545' if size_mb > 5 else '#28a745' if size_mb < 2 else '#ffc107'
            return format_html(
                '<span style="color: {}; font-weight: bold;">{} MB</span>',
                color,
                size_mb
            )
        return "—"
    file_size_display.short_description = 'Размер'


@admin.register(FeedbackReplyImage)
class FeedbackReplyImageAdmin(admin.ModelAdmin):
    """
    Админка для управления изображениями к ответам админа
    """
    list_display = ('id', 'reply_link', 'image_thumbnail', 'file_size_display', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('reply__reply_text', 'reply__admin__username')
    readonly_fields = ('image_large_preview', 'file_size_display', 'created_at')
    ordering = ('-created_at',)
    
    def reply_link(self, obj):
        """Ссылка на ответ"""
        url = reverse('admin:feedback_feedbackreply_change', args=[obj.reply.id])
        return format_html('<a href="{}">Ответ #{}</a>', url, obj.reply.id)
    reply_link.short_description = 'Ответ'
    
    def image_thumbnail(self, obj):
        """Миниатюра изображения"""
        if obj.image:
            return format_html(
                '<a href="{}" target="_blank"><img src="{}" style="max-height: 50px; max-width: 100px;"/></a>',
                obj.image.url,
                obj.image.url
            )
        return "—"
    image_thumbnail.short_description = 'Превью'
    
    def image_large_preview(self, obj):
        """Большое превью изображения"""
        if obj.image:
            return format_html(
                '<a href="{}" target="_blank"><img src="{}" style="max-width: 600px; border: 2px solid #ddd; border-radius: 8px;"/></a>',
                obj.image.url,
                obj.image.url
            )
        return "Нет изображения"
    image_large_preview.short_description = 'Изображение'
    
    def file_size_display(self, obj):
        """Отображение размера файла"""
        if obj.file_size:
            size_mb = obj.file_size_mb
            color = '#dc3545' if size_mb > 5 else '#28a745' if size_mb < 2 else '#ffc107'
            return format_html(
                '<span style="color: {}; font-weight: bold;">{} MB</span>',
                color,
                size_mb
            )
        return "—"
    file_size_display.short_description = 'Размер'


@admin.register(FeedbackReply)
class FeedbackReplyAdmin(admin.ModelAdmin):
    """
    Админка для управления ответами на сообщения поддержки
    """
    list_display = ('id', 'feedback_link', 'admin', 'short_reply', 'images_count_display', 'created_at', 'is_sent_to_user', 'sent_at', 'send_reply_link')
    list_filter = ('is_sent_to_user', 'created_at', 'admin')
    search_fields = ('reply_text', 'admin__username', 'feedback__message')
    readonly_fields = ('created_at', 'sent_at', 'send_error', 'images_preview')
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    inlines = [FeedbackReplyImageInline]
    
    def images_count_display(self, obj):
        """Отображение количества изображений в списке"""
        count = obj.images_count
        if count > 0:
            return format_html('<span style="color: #28a745;">📷 {}</span>', count)
        return "—"
    images_count_display.short_description = '📷'
    
    def images_preview(self, obj):
        """Превью всех изображений"""
        images = obj.images.all()
        if images:
            html = '<div style="display: flex; flex-wrap: wrap; gap: 10px;">'
            for img in images:
                html += format_html(
                    '<div style="text-align: center;">'
                    '<a href="{}" target="_blank">'
                    '<img src="{}" style="max-height: 150px; max-width: 200px; border: 2px solid #ddd; border-radius: 8px;"/>'
                    '</a>'
                    '<div style="font-size: 11px; color: #666; margin-top: 5px;">📦 {} MB</div>'
                    '</div>',
                    img.image.url,
                    img.image.url,
                    img.file_size_mb
                )
            html += '</div>'
            return mark_safe(html)
        return "Нет изображений"
    images_preview.short_description = 'Прикрепленные изображения'

    def feedback_link(self, obj):
        """Ссылка на сообщение поддержки"""
        url = reverse('admin:feedback_feedbackmessage_change', args=[obj.feedback.id])
        return format_html('<a href="{}">Сообщение #{}</a>', url, obj.feedback.id)
    feedback_link.short_description = 'Сообщение'

    def short_reply(self, obj):
        """Сокращенная версия ответа"""
        return obj.short_reply
    short_reply.short_description = 'Ответ'

    def has_add_permission(self, request):
        """Запрещаем создание ответов через админку"""
        return False

    def send_reply_action(self, request, reply_id):
        """Действие для отправки ответа"""
        try:
            if send_feedback_reply_to_telegram(reply_id):
                messages.success(request, "Ответ успешно отправлен пользователю")
            else:
                messages.error(request, "Ошибка отправки ответа")
        except Exception as e:
            messages.error(request, f"Ошибка: {str(e)}")
        
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/admin/'))

    def get_urls(self):
        """Добавляем кастомные URL для действий"""
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:reply_id>/send/',
                self.admin_site.admin_view(self.send_reply_action),
                name='feedback_feedbackreply_send',
            ),
        ]
        return custom_urls + urls

    def send_reply_link(self, obj):
        """Ссылка для отправки ответа"""
        if not obj.is_sent_to_user:
            url = reverse('admin:feedback_feedbackreply_send', args=[obj.id])
            return format_html('<a href="{}" class="button">Отправить ответ</a>', url)
        else:
            return format_html('<span style="color: green;">✅ Отправлено</span>')
    send_reply_link.short_description = 'Действие'
