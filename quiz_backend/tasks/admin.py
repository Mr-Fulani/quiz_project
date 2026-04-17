import os
import random
import time
from django import forms
from django.contrib import admin, messages
from django.urls import path, reverse
from django.shortcuts import render, redirect
from django.conf import settings
from django.utils.html import format_html, mark_safe
from django.utils import timezone
from .models import Task, TaskTranslation, TaskStatistics, TaskPoll, MiniAppTaskStatistics, TaskComment, TaskCommentImage, TaskCommentReport, SocialMediaPost, BackgroundMusic
from .services.task_import_service import import_tasks_from_json
from accounts.models import MiniAppUser
from .services.s3_service import delete_image_from_s3
from .services.telegram_service import publish_task_to_telegram, delete_message
from .services.image_generation_service import generate_image_for_task
from .services.s3_service import upload_image_to_s3
from webhooks.services import send_webhooks_for_task, send_webhooks_for_bulk_tasks
import uuid
import logging
from tenants.mixins import TenantFilteredAdminMixin

logger = logging.getLogger(__name__)


class TaskTranslationInline(admin.StackedInline):
    """
    Inline редактирование переводов задачи.
    Изменено на StackedInline для удобства редактирования новых полей.
    """
    model = TaskTranslation
    extra = 0
    fields = (
        'language', 'question', 'answers', 'correct_answer', 
        'explanation', 'long_explanation', 'source_name', 'source_link'
    )
    readonly_fields = ('publish_date',)


class SocialMediaPostInline(admin.TabularInline):
    """
    Inline для отображения публикаций в социальных сетях.
    """
    model = SocialMediaPost
    extra = 0
    fields = ('platform', 'method', 'status', 'post_url_display', 'created_at', 'published_at', 'retry_count', 'error_message')
    readonly_fields = ('platform', 'method', 'status', 'post_url_display', 'created_at', 'published_at', 'retry_count', 'error_message')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        """Запрещаем добавление публикаций вручную"""
        return False
    
    def post_url_display(self, obj):
        """Отображение ссылки на пост"""
        if obj.post_url:
            return format_html(
                '<a href="{}" target="_blank">🔗 Открыть пост</a>',
                obj.post_url
            )
        return '—'
    post_url_display.short_description = 'Ссылка на пост'


class TaskAdminForm(forms.ModelForm):
    """
    Кастомная форма для Task с выпадающим списком ссылок.
    Подтягивает все DefaultLink из общей БД с ботом.
    """
    # Кастомное поле для текста вопроса видео (простое текстовое поле вместо JSON)
    video_question_text = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'size': 80}),
        help_text='Кастомный текст вопроса для видео. Будет использован для языка текущего перевода задачи. Если не указан, используется дефолтный текст.'
    )
    
    class Meta:
        model = Task
        fields = '__all__'
        widgets = {
            'custom_webhook_links': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        from .services.default_link_service import DefaultLinkService
        
        # Получаем все DefaultLink + текущее значение для выпадающего списка
        default_links = DefaultLinkService.get_all_default_links()
        
        # Формируем choices
        choices = [('', '---Автоматически---')]
        
        # Если у задачи есть перевод, показываем какие ссылки будут использованы
        if self.instance.pk:
            translation = self.instance.translations.first()
            if translation:
                # Показываем специфичную ссылку для темы (если есть)
                if self.instance.topic:
                    topic_link = DefaultLinkService.get_default_link(
                        translation.language,
                        self.instance.topic.name
                    )
                    if topic_link:
                        choices.append((topic_link, f'🎯 Для темы {translation.language.upper()} + {self.instance.topic.name}: {topic_link}'))
                
                # Показываем главную ссылку для языка (ОБЯЗАТЕЛЬНА!)
                main_link = DefaultLinkService.get_main_fallback_link(translation.language)
                if main_link:
                    choices.append((main_link, f'🌐 Главная для {translation.language.upper()}: {main_link}'))
                else:
                    # ПРЕДУПРЕЖДЕНИЕ: нет главной ссылки!
                    choices.append(('', f'⚠️ НЕТ главной ссылки для {translation.language.upper()}! Создайте в: Webhooks → Main fallback links'))
                
                # Загружаем кастомный текст вопроса для текущего языка перевода
                if self.instance.video_question_texts and isinstance(self.instance.video_question_texts, dict):
                    current_text = self.instance.video_question_texts.get(translation.language, '')
                    self.fields['video_question_text'].initial = current_text
        
        # Добавляем остальные ссылки из общей БД
        for link in default_links:
            if not any(link == c[0] for c in choices):
                choices.append((link, link))
        
        # Если есть текущее значение и его нет в списке - добавляем
        if self.instance.external_link and self.instance.external_link not in [c[0] for c in choices]:
            choices.append((self.instance.external_link, f'✏️ Текущая: {self.instance.external_link}'))
        
        self.fields['external_link'].widget = forms.Select(choices=choices)
        self.fields['external_link'].required = False
        self.fields['external_link'].help_text = (
            'Ссылка для кнопки "Узнать больше о задаче" в Telegram. '
            'Если не указано, автоматически подбирается: для темы → главная для языка → резервная'
        )
        
        # Скрываем оригинальное поле video_question_texts (используем кастомное)
        if 'video_question_texts' in self.fields:
            self.fields['video_question_texts'].widget = forms.HiddenInput()
        
        # Делаем некоторые поля необязательными при редактировании существующей задачи
        if self.instance.pk:
            # При редактировании message_id не обязателен (он заполняется автоматически)
            if 'message_id' in self.fields:
                self.fields['message_id'].required = False
            
            # group может быть пустым (заполняется при импорте или можно выбрать позже)
            if 'group' in self.fields:
                self.fields['group'].required = False
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Сохраняем текст вопроса в video_question_texts по языку текущего перевода
        video_question_text = self.cleaned_data.get('video_question_text', '').strip()
        
        # Получаем перевод (после сохранения задачи переводы будут доступны)
        translation = instance.translations.first() if instance.pk else None
        
        if translation:
            language = translation.language
            if not instance.video_question_texts:
                instance.video_question_texts = {}
            
            if video_question_text:
                instance.video_question_texts[language] = video_question_text
            else:
                # Удаляем пустой текст для этого языка
                if language in instance.video_question_texts:
                    del instance.video_question_texts[language]
        
        if commit:
            instance.save()
        return instance


@admin.register(Task)
class TaskAdmin(TenantFilteredAdminMixin, admin.ModelAdmin):
    """
    Админка для управления задачами с расширенной функциональностью:
    - Импорт из JSON
    - Публикация в Telegram
    - Генерация изображений
    - Умное удаление с очисткой S3
    """
    form = TaskAdminForm
    change_list_template = 'admin/tasks/task_changelist.html'
    
    list_display = (
        'id', 'topic', 'subtopic', 'get_language', 'difficulty',
        'publication_status_display', 'telegram_group_display',
        'error_status', 'create_date', 'has_image', 'has_video',
    )
    list_filter = (
        'published_telegram', 'published_website', 'published_mini_app',
        'tenant', 'difficulty', 'topic', 'subtopic', 'error', 'translations__language',
    )
    search_fields = ('id', 'topic__name', 'subtopic__name', 'translation_group_id', 'external_link', 'translations__language')
    raw_id_fields = ('topic', 'subtopic', 'group', 'background_music')
    date_hierarchy = 'create_date'
    ordering = ('-create_date',)
    list_per_page = 20
    
    def _pause_between_task_publications(self, request, task_id):
        """
        Вставляет случайную паузу между публикациями задач (чтобы не воспринималось как спам).
        """
        pause_seconds = random.randint(3, 6)
        time.sleep(pause_seconds)
        self.message_user(
            request,
            f"⏸️ Пауза {pause_seconds} сек перед следующей задачей (последняя: {task_id})",
            messages.INFO
        )

    fieldsets = (
        ('📚 Основная информация', {
            'fields': ('topic', 'subtopic', 'difficulty')
        }),
        ('📡 Публикация по платформам', {
            'fields': ('published_telegram', 'published_website', 'published_mini_app', 'group'),
            'description': (
                'Укажите где задача опубликована. '
                'Telegram-канал (поле «group») можно назначить позже — задача создаётся и без него.'
            )
        }),
        ('🖹 Контент', {
            'fields': ('image_url', 'external_link', 'get_final_link_display'),
            'description': 'Ссылка используется для кнопки "Узнать больше" при публикации в Telegram'
        }),
        ('⚠️ Ошибки', {
            'fields': ('error',)
        }),
        ('ℹ️ Системная информация', {
            'fields': ('translation_group_id', 'message_id', 'create_date', 'publish_date'),
            'classes': ('collapse',)
        }),
        ('🎬 Действия', {
            'fields': ('generate_video_button',),
            'description': 'Быстрые действия для задачи'
        }),
        ('🎵 Видео', {
            'fields': ('background_music', 'video_question_text', 'video_urls_display', 'video_generation_logs_display'),
            'description': (
                'Информация о видео задачи. Можно выбрать конкретный трек для этой задачи '
                '(переопределяет автоматический выбор). '
                'Кастомный текст вопроса для видео будет использован для языка текущего перевода.'
            ),
            'classes': ()
        }),
    )
    readonly_fields = ('create_date', 'publish_date', 'translation_group_id', 'message_id', 'get_final_link_display', 'generate_video_button', 'video_urls_display', 'video_generation_logs_display')
    
    # Inline редактирование переводов и соцсетей
    inlines = [TaskTranslationInline, SocialMediaPostInline]
    
    actions = [
        'publish_to_telegram',
        'send_webhooks_separately',
        'generate_images',
        'generate_videos',
        'publish_to_all_social_networks',
        'publish_to_pinterest',
        'publish_to_facebook',
        'publish_to_yandex_dzen',
        'publish_to_instagram',
        'publish_to_tiktok',
        'publish_to_youtube_shorts',
        'publish_to_instagram_reels',
        'publish_to_instagram_stories',
        'publish_to_facebook_stories',
        'publish_to_facebook_reels',
        'publish_with_auto_reshare',
        'clear_error_flag',
        'sync_with_telegram_groups'
    ]
    
    def save_related(self, request, form, formsets, change):
        """Сохраняет связанные объекты и обновляет video_question_texts после сохранения переводов."""
        super().save_related(request, form, formsets, change)
        
        # После сохранения всех inline объектов (включая переводы) обновляем video_question_texts
        instance = form.instance
        video_question_text = form.cleaned_data.get('video_question_text', '').strip()
        # Теперь переводы уже сохранены, можем получить язык
        translation = instance.translations.first()
        if translation and video_question_text:
            language = translation.language
            if not instance.video_question_texts:
                instance.video_question_texts = {}
            instance.video_question_texts[language] = video_question_text
            instance.save(update_fields=['video_question_texts'])
        elif translation and not video_question_text:
            # Удаляем пустой текст для этого языка
            if instance.video_question_texts and translation.language in instance.video_question_texts:
                del instance.video_question_texts[translation.language]
                instance.save(update_fields=['video_question_texts'])
        
    @admin.action(description="🔗 Привязать к Telegram группам (по теме и языку)")
    def sync_with_telegram_groups(self, request, queryset):
        """
        Массово привязывает задачи к Telegram-группам на основе темы и языка.
        """
        from tasks.services.group_sync_service import sync_tasks_with_groups
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            self.message_user(request, "❌ Тенант не определен. Не удалось выполнить синхронизацию.", messages.ERROR)
            return

        updated_count = sync_tasks_with_groups(tenant=tenant, task_queryset=queryset)
        
        self.message_user(
            request, 
            f"✅ Синхронизация завершена. Обновлено задач: {updated_count}", 
            messages.SUCCESS
        )
    
    def get_queryset(self, request):
        """Оптимизация запросов: предзагружаем переводы для отображения языка."""
        qs = super().get_queryset(request)
        return qs.select_related('topic', 'subtopic', 'group').prefetch_related('translations')
    
    def has_image(self, obj):
        """Проверка наличия изображения."""
        return bool(obj.image_url)
    has_image.boolean = True
    has_image.short_description = 'Изображение'
    
    def has_video(self, obj):
        """Проверка наличия видео."""
        # Проверяем наличие видео в новом поле video_urls или старом video_url
        return bool(obj.video_urls) or bool(obj.video_url)
    has_video.boolean = True
    has_video.short_description = 'Видео'
    
    def has_external_link(self, obj):
        """Проверка наличия внешней ссылки."""
        return bool(obj.external_link)
    has_external_link.boolean = True
    has_external_link.short_description = 'Ссылка "Подробнее"'
    
    def get_language(self, obj):
        """Отображение языка задачи из перевода."""
        translation = obj.translations.first()
        if translation:
            # Добавляем флаги для популярных языков
            flags = {
                'en': '🇬🇧',
                'ru': '🇷🇺',
                'tr': '🇹🇷',
                'ar': '🇸🇦',
                'es': '🇪🇸',
                'fr': '🇫🇷',
                'de': '🇩🇪',
                'zh': '🇨🇳',
                'ja': '🇯🇵',
                'ko': '🇰🇷',
                'it': '🇮🇹',
                'pt': '🇵🇹',
                'nl': '🇳🇱',
                'pl': '🇵🇱',
                'uk': '🇺🇦',
                'he': '🇮🇱',
                'hi': '🇮🇳',
                'th': '🇹🇭',
                'vi': '🇻🇳',
                'id': '🇮🇩',
                'sv': '🇸🇪',
                'no': '🇳🇴',
                'da': '🇩🇰',
                'fi': '🇫🇮',
                'cs': '🇨🇿',
                'hu': '🇭🇺',
                'ro': '🇷🇴',
                'bg': '🇧🇬',
                'el': '🇬🇷',
                'sk': '🇸🇰',
                'hr': '🇭🇷',
                'sr': '🇷🇸',
                'mk': '🇲🇰',
                'sq': '🇦🇱',
                'az': '🇦🇿',
                'kk': '🇰🇿',
                'uz': '🇺🇿',
                'ka': '🇬🇪',
                'hy': '🇦🇲',
                'be': '🇧🇾',
                'et': '🇪🇪',
                'lv': '🇱🇻',
                'lt': '🇱🇹',
                'is': '🇮🇸',
                'ga': '🇮🇪',
                'mt': '🇲🇹',
                'cy': '🇬🇧',
                'eu': '🇪🇸',
                'ca': '🇪🇸',
                'gl': '🇪🇸',
                'br': '🇫🇷',
                'eo': '🌍',
            }
            flag = flags.get(translation.language.lower(), '🌐')
            return format_html(
                '<span style="font-weight: bold;">{} {}</span>',
                flag,
                translation.language.upper()
            )
        return format_html('<span style="color: #dc3545;">—</span>')
    get_language.short_description = 'Язык'
    
    def publication_status_display(self, obj):
        """
        Цветные бейджи статуса публикации по трём платформам.
          🟢 зелёный  — опубликовано
          ⚫ серый    — не опубликовано
          🟡 жёлтый  — Telegram без канала (задача есть, но канал не назначен)
        """
        def badge(icon, label, color, text_color='white'):
            return (
                f'<span style="display:inline-block;background:{color};color:{text_color};'
                f'padding:2px 7px;border-radius:4px;font-size:11px;font-weight:600;'
                f'margin:1px;white-space:nowrap;">{icon} {label}</span>'
            )

        parts = []

        # Сайт
        if obj.published_website:
            parts.append(badge('🌐', 'Сайт', '#28a745'))
        else:
            parts.append(badge('🌐', 'Сайт', '#6c757d'))

        # Mini App
        if obj.published_mini_app:
            parts.append(badge('📱', 'App', '#28a745'))
        else:
            parts.append(badge('📱', 'App', '#6c757d'))

        # Telegram
        if obj.published_telegram:
            parts.append(badge('✈️', 'TG', '#28a745'))
        elif not obj.group:
            # Канал не назначен — предупреждение
            parts.append(badge('❗', 'Нет канала', '#ffc107', '#333'))
        else:
            # Канал есть, но ещё не опубликовано
            parts.append(badge('✈️', 'TG', '#dc3545'))

        return format_html('<div style="white-space:nowrap">{}</div>', mark_safe(''.join(parts)))

    publication_status_display.short_description = 'Публикация'

    def telegram_group_display(self, obj):
        """Показывает привязанный Telegram-канал или предупреждение."""
        if obj.group:
            return format_html(
                '<span style="color:#28a745;font-weight:600;">✅ {}</span>',
                obj.group.group_name
            )
        return format_html(
            '<span style="color:#dc3545;">❌ Не назначен</span>'
        )

    telegram_group_display.short_description = 'TG Канал'

    def error_status(self, obj):
        """Отображение статуса ошибки с цветовой индикацией."""
        if obj.error:
            return format_html(
                '<span style="color: #dc3545; font-weight: bold;">⚠️ Ошибка</span>'
            )
        else:
            return format_html(
                '<span style="color: #28a745;">✅ OK</span>'
            )
    error_status.short_description = 'Статус'

    
    def get_final_link_display(self, obj):
        """Отображает итоговую ссылку которая будет использована при публикации"""
        from .services.default_link_service import DefaultLinkService
        
        if not obj.pk:
            return "—"
        
        translation = obj.translations.first()
        final_link, source = DefaultLinkService.get_final_link(obj, translation)
        
        # Если ссылки нет - показываем предупреждение
        if final_link is None:
            return format_html(
                '⚠️ <span style="color: #dc3545; font-weight: bold;">НЕТ ССЫЛКИ!</span><br>'
                '<small style="color: #dc3545;">{}</small><br>'
                '<small style="color: #666;">Создайте главную ссылку в разделе: Webhooks → Main fallback links</small>',
                source
            )
        
        # Форматируем вывод с иконками
        if "вручную" in source:
            icon = "🔗"
            color = "#28a745"  # зеленый
        elif "для темы" in source:
            icon = "🎯"
            color = "#007bff"  # синий
        elif "главная" in source:
            icon = "🌐"
            color = "#ffc107"  # желтый
        else:
            icon = "❓"
            color = "#666"
        
        return format_html(
            '{} <a href="{}" target="_blank" style="color: {};">{}</a><br>'
            '<small style="color: #666;">Источник: {}</small>',
            icon,
            final_link,
            color,
            final_link[:60] + '...' if len(final_link) > 60 else final_link,
            source
        )
    get_final_link_display.short_description = 'Итоговая ссылка'
    
    def video_generation_logs_display(self, obj):
        """Отображение логов генерации видео с форматированием для светлой и темной темы."""
        if not obj.video_generation_logs:
            return format_html(
                '<div style="padding: 15px; border: 1px solid #dee2e6; border-radius: 5px; background: #f8f9fa; color: #6c757d;">'
                '📋 <strong>Логи генерации видео отсутствуют</strong><br>'
                'Логи появятся здесь после запуска генерации видео через кнопку "Сгенерировать видео" выше.'
                '</div>'
            )
        
        from django.utils.safestring import mark_safe
        from django.utils.html import escape
        
        # Обрабатываем логи
        logs_text = obj.video_generation_logs
        
        # Если в логах есть <br> как текст, заменяем на реальные переносы
        logs_text = logs_text.replace('<br>', '\n').replace('<br />', '\n').replace('<BR>', '\n')
        
        # Разбиваем на строки для обработки
        lines = logs_text.split('\n')
        processed_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Обрабатываем разделители (строки с символами ═)
            if '════════════════════════════════════════════════' in line:
                # Если есть emoji в начале, оставляем его
                if line.startswith('🎬') or line.startswith('❌'):
                    processed_lines.append(f'<div class="log-separator-line">{escape(line[:2])}</div>')
                else:
                    processed_lines.append('<div class="log-separator-line"></div>')
            else:
                # Обычная строка - экранируем и добавляем
                processed_lines.append(escape(line))
        
        # Объединяем строки с правильными переносами
        logs_html = mark_safe('<br>'.join(processed_lines))
        
        # Универсальные стили, которые работают в любой теме админки
        return format_html(
            '<style>'
            '.video-logs-container {{'
            '  padding: 15px;'
            '  border-radius: 5px;'
            '  font-family: "Consolas", "Monaco", "Courier New", monospace;'
            '  font-size: 13px;'
            '  line-height: 1.8;'
            '  max-height: 400px;'
            '  overflow-y: auto;'
            '  word-wrap: break-word;'
            '  border: 1px solid #dee2e6;'
            '  background: #f8f9fa;'
            '  color: #212529;'
            '  box-shadow: 0 1px 3px rgba(0,0,0,0.1);'
            '}}'
            '.video-logs-container br {{'
            '  display: block;'
            '  margin: 2px 0;'
            '}}'
            # Стили для разделителей
            '.video-logs-container .log-separator-line {{'
            '  margin: 12px 0;'
            '  padding: 8px 0;'
            '  border-top: 1px solid #dee2e6;'
            '  text-align: center;'
            '  color: #6c757d;'
            '  font-size: 12px;'
            '}}'
            # Темная тема - различные варианты определения
            'body.dark-theme .video-logs-container,'
            'body[data-theme="dark"] .video-logs-container,'
            '.theme-dark .video-logs-container,'
            '.admin-dark .video-logs-container {{'
            '  background: #1e1e1e !important;'
            '  color: #d4d4d4 !important;'
            '  border-color: #3c3c3c !important;'
            '  box-shadow: 0 1px 3px rgba(0,0,0,0.3) !important;'
            '}}'
            'body.dark-theme .video-logs-container .log-separator-line,'
            'body[data-theme="dark"] .video-logs-container .log-separator-line,'
            '.theme-dark .video-logs-container .log-separator-line,'
            '.admin-dark .video-logs-container .log-separator-line {{'
            '  border-top-color: #3c3c3c !important;'
            '  color: #888 !important;'
            '}}'
            # Если body имеет темный фон
            'body[style*="background"][style*="dark"] .video-logs-container,'
            'body[style*="background-color: #121212"] .video-logs-container,'
            'body[style*="background-color: #1a1a1a"] .video-logs-container {{'
            '  background: #1e1e1e !important;'
            '  color: #d4d4d4 !important;'
            '  border-color: #3c3c3c !important;'
            '}}'
            # Медиа-запрос для системной темной темы
            '@media (prefers-color-scheme: dark) {{'
            '  .video-logs-container {{'
            '    background: #1e1e1e;'
            '    color: #d4d4d4;'
            '    border-color: #3c3c3c;'
            '  }}'
            '  .video-logs-container .log-separator-line {{'
            '    border-top-color: #3c3c3c;'
            '    color: #888;'
            '  }}'
            '}}'
            '</style>'
            '<div class="video-logs-container">{}</div>',
            logs_html
        )
    video_generation_logs_display.short_description = 'Логи генерации видео'
    
    def generate_video_button(self, obj):
        """Кнопка для генерации видео в детальном просмотре задачи."""
        if not obj.pk:
            return "—"

        # Проверяем, есть ли переводы
        translations = list(obj.translations.all())
        if not translations:
            return format_html('<span style="color: #dc3545;">⚠️ Нет переводов для генерации видео</span>')

        # Проверяем, есть ли уже видео (в новом или старом поле)
        existing_videos = []
        if obj.video_urls:
            existing_videos = list(obj.video_urls.keys())
        elif obj.video_url:
            existing_videos = ['ru']  # Старое видео считается русским

        # Основной перевод (первый)
        main_translation = translations[0]
        main_lang = main_translation.language
        generate_url = reverse('admin:tasks_task_generate_video', args=[obj.pk])

        # Кнопка для основного языка
        if main_lang in existing_videos:
            button_html = (
                f'<a href="{generate_url}" class="button" style="background: #28a745; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px; display: inline-block;">'
                f'🎬 Перегенерировать видео ({main_lang.upper()})'
                '</a>'
            )
        else:
            button_html = (
                f'<a href="{generate_url}" class="button" style="background: #007bff; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px; display: inline-block;">'
                f'🎬 Сгенерировать видео ({main_lang.upper()})'
                '</a>'
            )

        # Ссылки на существующие видео
        video_links = []
        for lang in existing_videos:
            if lang in obj.video_urls:
                video_links.append(f'<a href="{obj.video_urls[lang]}" target="_blank" style="color: #007bff; text-decoration: none; margin-right: 10px; font-weight: bold;">🔗 {lang.upper()}</a>')

        return format_html(
            '<div style="margin: 10px 0;">'
            '{}'
            '{}'
            '<p style="margin-top: 10px; color: #666; font-size: 12px;">Видео генерируется для основного языка задачи</p>'
            '</div>',
            mark_safe(button_html),
            mark_safe('<div style="margin-top: 8px;">' + ''.join(video_links) + '</div>') if video_links else ''
        )
    generate_video_button.short_description = 'Генерация видео'

    @admin.display(description='URL видео по языкам')
    def video_urls_display(self, obj):
        """Отображение всех URL видео по языкам."""
        if not obj.video_urls and not obj.video_url:
            return "Видео не сгенерировано"

        html_parts = []
        if obj.video_urls:
            for lang, url in obj.video_urls.items():
                html_parts.append(f'<div><strong>{lang.upper()}:</strong> <a href="{url}" target="_blank" style="color: #007bff; text-decoration: underline;">{url}</a></div>')
        elif obj.video_url:
            html_parts.append(f'<div><strong>RU (старое поле):</strong> <a href="{obj.video_url}" target="_blank" style="color: #007bff; text-decoration: underline;">{obj.video_url}</a></div>')

        return mark_safe(''.join(html_parts))

    def get_urls(self):
        """Добавляем URL для импорта JSON и генерации видео."""
        urls = super().get_urls()
        custom_urls = [
            path('import-json/', self.admin_site.admin_view(self.import_json_view), name='tasks_task_import_json'),
            path('<path:object_id>/generate-video/', self.admin_site.admin_view(self.generate_video_view), name='tasks_task_generate_video'),
        ]
        return custom_urls + urls
    
    def import_json_view(self, request):
        """
        Представление для импорта задач из JSON файла или текста.
        """
        if request.method == 'POST':
            json_file = request.FILES.get('json_file')
            json_text = request.POST.get('json_text', '').strip()
            publish = request.POST.get('publish') == 'on'
            
            # Проверяем, что хотя бы один источник данных указан
            if not json_file and not json_text:
                messages.error(request, 'Пожалуйста, выберите JSON файл или вставьте текст.')
                return render(request, 'admin/tasks/import_json.html')
            
            # Определяем источник и создаем временный файл
            temp_path = None
            
            if json_text:
                # Импорт из текста
                import json
                # Валидируем JSON
                try:
                    json.loads(json_text)
                except json.JSONDecodeError as e:
                    messages.error(request, f'Некорректный JSON: {str(e)}')
                    return render(request, 'admin/tasks/import_json.html')
                
                # Сохраняем текст во временный файл
                temp_path = os.path.join(settings.MEDIA_ROOT, 'temp', f'json_text_{uuid.uuid4()}.json')
                os.makedirs(os.path.dirname(temp_path), exist_ok=True)
                
                with open(temp_path, 'w', encoding='utf-8') as f:
                    f.write(json_text)
            else:
                # Импорт из файла
                temp_path = os.path.join(settings.MEDIA_ROOT, 'temp', json_file.name)
                os.makedirs(os.path.dirname(temp_path), exist_ok=True)
                
                with open(temp_path, 'wb+') as destination:
                    for chunk in json_file.chunks():
                        destination.write(chunk)
            
            try:
                # Получаем тенанта из запроса (устанавливается TenantMiddleware)
                tenant = getattr(request, 'tenant', None)
                # Импортируем задачи
                result = import_tasks_from_json(temp_path, publish=publish, tenant=tenant)
                
                # Удаляем временный файл
                os.remove(temp_path)
                
                # Показываем детальные логи процесса импорта
                if result.get('detailed_logs'):
                    for log in result['detailed_logs']:
                        # Определяем уровень сообщения по emoji
                        if log.startswith('✅'):
                            messages.success(request, log)
                        elif log.startswith('📄') or log.startswith('📊') or log.startswith('📂') or log.startswith('📎'):
                            messages.info(request, log)
                        elif log.startswith('🎨') or log.startswith('📢'):
                            messages.success(request, log)
                        elif log.startswith('⚠️'):
                            messages.warning(request, log)
                        elif log.startswith('❌'):
                            messages.error(request, log)
                        elif log.startswith('='):
                            messages.info(request, log)
                        else:
                            messages.info(request, log)
                
                # Дополнительное итоговое сообщение
                if result['successfully_loaded'] > 0:
                    task_ids = ', '.join(map(str, result['successfully_loaded_ids'][:10]))
                    if len(result['successfully_loaded_ids']) > 10:
                        task_ids += f" ... (еще {len(result['successfully_loaded_ids']) - 10})"
                    messages.success(
                        request,
                        f"🎯 ID загруженных задач: {task_ids}"
                    )
                
                # Ошибки (если есть детальные логи, то показываем только итог)
                for error in result['error_messages'][:3]:
                    if error not in result.get('detailed_logs', []):
                        messages.error(request, error)
                
                for error in result['publish_errors'][:3]:
                    if error not in result.get('detailed_logs', []):
                        messages.warning(request, f"Ошибка публикации: {error}")
                
                return redirect('admin:tasks_task_changelist')
                
            except Exception as e:
                logger.error(f"Ошибка импорта JSON: {e}")
                messages.error(request, f'Ошибка импорта: {str(e)}')
                # Удаляем временный файл при ошибке
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        
        return render(request, 'admin/tasks/import_json.html')
    
    def generate_video_view(self, request, object_id):
        """
        Представление для генерации видео для конкретной задачи.
        Поддерживает генерацию для конкретного языка через параметр language=xx
        """
        from config.tasks import generate_video_for_task_async

        try:
            task = Task.objects.get(pk=object_id)
        except Task.DoesNotExist:
            messages.error(request, f'Задача с ID {object_id} не найдена.')
            return redirect('admin:tasks_task_changelist')

        # Получаем параметр языка
        requested_language = request.GET.get('language')

        # Если указан конкретный язык, генерируем только для него
        if requested_language:
            translation = task.translations.filter(language=requested_language).first()
            if not translation:
                messages.error(request, f'Задача {task.id} не имеет перевода на язык {requested_language}.')
                return redirect('admin:tasks_task_change', object_id)
            translations = [translation]
            mode_text = f"для языка {requested_language}"
        else:
            # По умолчанию генерируем для первого перевода (основной язык)
            translation = task.translations.first()
            if not translation:
                messages.error(request, f'Задача {task.id} не имеет переводов.')
                return redirect('admin:tasks_task_change', object_id)
            translations = [translation]
            mode_text = f"для языка {translation.language}"

        try:
            # Получаем информацию о теме и подтеме
            topic_name = task.topic.name if task.topic else 'unknown'
            subtopic_name = task.subtopic.name if task.subtopic else None
            difficulty = task.difficulty if hasattr(task, 'difficulty') else None

            # Получаем admin_chat_id для отправки видео админу
            from django.conf import settings
            admin_chat_id = getattr(settings, 'TELEGRAM_ADMIN_CHAT_ID', None)

            # Если не задан в настройках, пытаемся получить из базы (первый активный админ)
            if not admin_chat_id:
                try:
                    from accounts.models import TelegramAdmin
                    admin = TelegramAdmin.objects.filter(is_active=True).first()
                    if admin:
                        admin_chat_id = str(admin.telegram_id)
                        logger.info(f"📱 Используется chat_id первого активного админа для генерации видео: {admin_chat_id}")
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось получить chat_id админа из базы: {e}")

            # Очищаем старые логи перед запуском новой генерации
            task.video_generation_logs = None
            task.save(update_fields=['video_generation_logs'])

            # Определяем языки для генерации видео
            languages_to_generate = [trans.language for trans in translations]
            task.video_generation_progress = {lang: False for lang in languages_to_generate}
            task.save(update_fields=['video_generation_progress'])

            # Запускаем асинхронную генерацию видео для выбранных языков
            celery_tasks = []
            for translation in translations:
                celery_task = generate_video_for_task_async.delay(
                    task_id=task.id,
                    task_question=translation.question,
                    topic_name=topic_name,
                    subtopic_name=subtopic_name,
                    difficulty=difficulty,
                    force_regenerate=True,  # Принудительная перегенерация при ручном запуске
                    admin_chat_id=admin_chat_id,  # Передаем admin_chat_id для отправки видео
                    video_language=translation.language,  # Язык видео
                    expected_languages=languages_to_generate  # Все ожидаемые языки
                )
                celery_tasks.append(celery_task)

            languages_text = ", ".join(languages_to_generate)
            messages.success(request, f'✅ Генерация видео для задачи {task.id} запущена {mode_text}: {languages_text}!')
            messages.info(request, f'📝 Celery tasks: {", ".join([str(task.id) for task in celery_tasks])}')
            messages.info(request, f'💡 Видео будет сгенерировано в фоне и отправлено админу в личку бота')
            messages.info(request, f'🔍 Статус генерации можно отследить в разделе "Видео" ниже')

        except Exception as e:
            logger.error(f"Ошибка запуска генерации видео для задачи {task.id}: {e}", exc_info=True)
            messages.error(request, f'❌ Ошибка запуска генерации видео: {str(e)}')

        return redirect('admin:tasks_task_change', object_id)
    
    def get_deleted_objects(self, objs, request):
        """
        Переопределяем метод для отображения всех связанных задач, 
        которые будут удалены вместе с выбранными.
        Показывает все связанные сущности: переводы, статистику, опросы, комментарии и т.д.
        """
        from django.contrib.admin.utils import NestedObjects
        from django.db import router
        from .models import TaskTranslation, TaskStatistics, MiniAppTaskStatistics, TaskPoll
        
        collector = NestedObjects(using=router.db_for_write(Task))
        
        # Для каждого объекта находим все связанные задачи по translation_group_id
        all_tasks_to_delete = set()
        for obj in objs:
            if obj.translation_group_id:
                related_tasks = Task.objects.filter(
                    translation_group_id=obj.translation_group_id
                ).select_related('topic', 'subtopic', 'group').prefetch_related('translations')
                all_tasks_to_delete.update(related_tasks)
            else:
                # Предзагружаем связи для одиночной задачи
                obj = Task.objects.select_related('topic', 'subtopic', 'group').prefetch_related('translations').get(pk=obj.pk)
                all_tasks_to_delete.add(obj)
        
        # Собираем все объекты для удаления (NestedObjects автоматически соберет все связанные через CASCADE)
        collector.collect(list(all_tasks_to_delete))
        
        # Получаем стандартное представление удаляемых объектов
        perms_needed = set()
        protected = []
        
        def format_callback(obj):
            """Форматирование названия объекта для отображения"""
            opts = obj._meta
            no_edit_link = f'{opts.verbose_name}: {obj}'
            
            # Для задач показываем язык
            if isinstance(obj, Task):
                translation = obj.translations.first()
                if translation:
                    return f'{opts.verbose_name}: {obj} ({translation.language.upper()})'
                return no_edit_link
            
            # Для переводов показываем язык
            if isinstance(obj, TaskTranslation):
                return f'{opts.verbose_name}: {obj.task_id} ({obj.language.upper()})'
            
            # Для статистики показываем пользователя
            if isinstance(obj, TaskStatistics):
                return f'{opts.verbose_name}: Задача {obj.task_id} - Пользователь {obj.user_id}'
            
            # Для статистики мини-аппа
            if isinstance(obj, MiniAppTaskStatistics):
                return f'{opts.verbose_name}: Задача {obj.task_id} - Mini App пользователь {obj.mini_app_user_id}'
            
            # Для опросов
            if isinstance(obj, TaskPoll):
                return f'{opts.verbose_name}: {obj.poll_id} (Задача {obj.task_id})'
            
            # Стандартное форматирование для остальных
            return no_edit_link
        
        to_delete = collector.nested(format_callback)
        
        # Считаем количество объектов каждого типа
        model_count = {}
        if hasattr(collector, 'model_objs') and collector.model_objs:
            for model, objs_list in collector.model_objs.items():
                count = len(objs_list)
                if count > 0:
                    # Используем verbose_name_plural для отображения
                    verbose_name = model._meta.verbose_name_plural
                    model_count[verbose_name] = count
        
        # Добавляем информацию об изображениях S3, которые будут удалены
        image_urls = set()
        telegram_messages_count = 0
        telegram_channels = set()
        
        for task in all_tasks_to_delete:
            if task.image_url:
                image_urls.add(task.image_url)
            
            # Подсчитываем задачи, которые имеют опубликованные сообщения в Telegram
            if task.published and task.message_id and task.group:
                telegram_messages_count += 1
                if task.group.group_name:
                    telegram_channels.add(task.group.group_name)
        
        # Преобразуем to_delete в список, если это не список
        if isinstance(to_delete, tuple):
            to_delete = list(to_delete)
        elif not isinstance(to_delete, list):
            to_delete = [str(to_delete)] if to_delete else []
        
        # Вставляем предупреждения в начало списка
        warnings = []
        
        # Информация об удалении сообщений из Telegram
        if telegram_messages_count > 0:
            channels_info = f" ({', '.join(sorted(telegram_channels))})" if telegram_channels else ""
            telegram_info = f"📱 Telegram: {telegram_messages_count} опубликованная задача(и) будет удалена из каналов{channels_info}. Сообщения (фото, текст, опрос, кнопка) будут удалены из Telegram каналов, если бот имеет необходимые права."
            warnings.append(telegram_info)
        
        # Информация об изображениях S3
        if image_urls:
            image_info = f"🖼️ Изображения в S3: {len(image_urls)} файл(ов) будет удален"
            warnings.append(image_info)
        
        # Вставляем предупреждения в начало списка
        for warning in reversed(warnings):
            to_delete.insert(0, warning)
        
        return to_delete, model_count, perms_needed, protected
    
    def delete_model(self, request, obj):
        """
        Переопределяем удаление одной задачи для очистки связанных ресурсов.
        Удаляет все связанные задачи по translation_group_id, их изображения из S3
        и сообщения из Telegram каналов (если бот имеет права).
        """
        translation_group_id = obj.translation_group_id
        
        if translation_group_id:
            # Находим все связанные задачи
            related_tasks = Task.objects.filter(translation_group_id=translation_group_id).select_related('group')
            
            # Собираем информацию о языках ДО удаления
            languages = []
            deleted_messages_count = 0
            failed_messages_count = 0
            
            for task in related_tasks:
                translation = task.translations.first()
                if translation:
                    languages.append(translation.language.upper())
                
                # Удаляем сообщения из Telegram каналов, если задача была опубликована
                if task.published and task.message_id and task.group:
                    try:
                        chat_id = str(task.group.group_id)
                        logger.info(f"🗑️ Попытка удаления сообщений для задачи {task.id}: message_id={task.message_id}, chat_id={chat_id}")
                        # Пробуем удалить несколько сообщений подряд (фото, текст, опрос, кнопка)
                        # Обычно опрос имеет message_id, а остальные сообщения идут рядом
                        for offset in range(-2, 2):  # -2, -1, 0, 1 (покрываем 4 сообщения)
                            message_id_to_delete = task.message_id + offset
                            logger.debug(f"   Попытка удалить message_id {message_id_to_delete} (offset={offset})")
                            if delete_message(chat_id, message_id_to_delete):
                                deleted_messages_count += 1
                                logger.info(f"   ✅ Удалено сообщение {message_id_to_delete}")
                            else:
                                failed_messages_count += 1
                                logger.debug(f"   ⚠️ Не удалось удалить сообщение {message_id_to_delete}")
                    except Exception as e:
                        logger.warning(f"Ошибка при удалении сообщений для задачи {task.id}: {e}", exc_info=True)
                        failed_messages_count += 1
                else:
                    logger.debug(f"⚠️ Задача {task.id} пропущена при удалении сообщений: published={task.published}, message_id={task.message_id}, group={task.group}")
            
            # Собираем URL изображений ОДИН РАЗ
            image_urls = list(set([task.image_url for task in related_tasks if task.image_url]))
            
            count = related_tasks.count()
            
            # Удаляем изображения из S3
            for image_url in image_urls:
                delete_image_from_s3(image_url)
            
            # Удаляем все связанные задачи
            related_tasks.delete()
            
            lang_info = ", ".join(languages) if languages else ""
            message_info = ""
            if deleted_messages_count > 0:
                message_info = f", удалено {deleted_messages_count} сообщений из Telegram"
            if failed_messages_count > 0:
                message_info += f" ({failed_messages_count} сообщений не удалось удалить - возможно, нет прав бота или сообщения уже удалены)"
            
            messages.success(
                request,
                f"Удалено {count} связанных задач ({lang_info}) и {len(image_urls)} изображений из S3{message_info}"
            )
        else:
            # Обычное удаление одной задачи
            if obj.published and obj.message_id and obj.group:
                try:
                    chat_id = str(obj.group.group_id)
                    logger.info(f"🗑️ Попытка удаления сообщений для задачи {obj.id}: message_id={obj.message_id}, chat_id={chat_id}")
                    # Пробуем удалить несколько сообщений подряд
                    for offset in range(-2, 2):
                        message_id_to_delete = obj.message_id + offset
                        logger.debug(f"   Попытка удалить message_id {message_id_to_delete} (offset={offset})")
                        delete_message(chat_id, message_id_to_delete)
                except Exception as e:
                    logger.warning(f"Ошибка при удалении сообщений для задачи {obj.id}: {e}", exc_info=True)
            else:
                logger.debug(f"⚠️ Задача {obj.id} пропущена при удалении сообщений: published={obj.published}, message_id={obj.message_id}, group={obj.group}")
            
            super().delete_model(request, obj)
    
    def delete_queryset(self, request, queryset):
        """
        Переопределяем массовое удаление для очистки связанных ресурсов.
        Удаляет задачи, изображения из S3 и сообщения из Telegram каналов.
        """
        # Собираем все translation_group_id
        translation_group_ids = set(
            queryset.values_list('translation_group_id', flat=True)
        )
        
        # Находим все связанные задачи
        all_related_tasks = Task.objects.filter(
            translation_group_id__in=translation_group_ids
        ).select_related('group')
        
        # Собираем информацию о языках ДО удаления
        languages = []
        deleted_messages_count = 0
        failed_messages_count = 0
        
        for task in all_related_tasks:
            translation = task.translations.first()
            if translation:
                languages.append(translation.language.upper())
            
            # Удаляем сообщения из Telegram каналов, если задача была опубликована
            if task.published and task.message_id and task.group:
                try:
                    chat_id = str(task.group.group_id)
                    logger.info(f"🗑️ Попытка удаления сообщений для задачи {task.id}: message_id={task.message_id}, chat_id={chat_id}")
                    # Пробуем удалить несколько сообщений подряд (фото, текст, опрос, кнопка)
                    for offset in range(-2, 2):  # -2, -1, 0, 1 (покрываем 4 сообщения)
                        message_id_to_delete = task.message_id + offset
                        logger.debug(f"   Попытка удалить message_id {message_id_to_delete} (offset={offset})")
                        if delete_message(chat_id, message_id_to_delete):
                            deleted_messages_count += 1
                            logger.info(f"   ✅ Удалено сообщение {message_id_to_delete}")
                        else:
                            failed_messages_count += 1
                            logger.debug(f"   ⚠️ Не удалось удалить сообщение {message_id_to_delete}")
                except Exception as e:
                    logger.warning(f"Ошибка при удалении сообщений для задачи {task.id}: {e}", exc_info=True)
                    failed_messages_count += 1
            else:
                logger.debug(f"⚠️ Задача {task.id} пропущена при удалении сообщений: published={task.published}, message_id={task.message_id}, group={task.group}")
        
        # Собираем URL изображений ОДИН РАЗ (используем set для уникальности)
        image_urls = list(set([task.image_url for task in all_related_tasks if task.image_url]))
        
        count = all_related_tasks.count()
        
        # Удаляем изображения из S3
        deleted_images = 0
        for image_url in image_urls:
            if delete_image_from_s3(image_url):
                deleted_images += 1
        
        # Удаляем все связанные задачи
        all_related_tasks.delete()
        
        lang_info = ", ".join(sorted(set(languages))) if languages else ""
        message_info = ""
        if deleted_messages_count > 0:
            message_info = f", удалено {deleted_messages_count} сообщений из Telegram"
        if failed_messages_count > 0:
            message_info += f" ({failed_messages_count} сообщений не удалось удалить - возможно, нет прав бота или сообщения уже удалены)"
        
        messages.success(
            request,
            f"Удалено {count} задач ({lang_info}) и {deleted_images} изображений из S3{message_info}"
        )
    
    @admin.action(description='Опубликовать выбранные задачи в Telegram')
    def publish_to_telegram(self, request, queryset):
        """
        Публикует выбранные задачи в Telegram с детальными логами.
        Автоматически находит и публикует все связанные переводы по translation_group_id.
        """
        from platforms.models import TelegramGroup
        
        # Собираем все translation_group_id
        translation_group_ids = set(
            queryset.values_list('translation_group_id', flat=True)
        )
        
        # Находим все связанные задачи
        all_related_tasks = Task.objects.filter(
            translation_group_id__in=translation_group_ids
        ).select_related('topic', 'subtopic', 'group').prefetch_related('translations')
        
        # Группируем задачи по языкам для информирования
        tasks_by_language = {}
        for task in all_related_tasks:
            translation = task.translations.first()
            if translation:
                lang = translation.language.upper()
                if lang not in tasks_by_language:
                    tasks_by_language[lang] = []
                tasks_by_language[lang].append(task)
        
        total_tasks = all_related_tasks.count()
        selected_count = queryset.count()
        
        # Информируем пользователя о масштабе операции
        self.message_user(
            request,
            f"📊 Выбрано задач: {selected_count}",
            messages.INFO
        )
        self.message_user(
            request,
            f"🌍 Найдено связанных переводов: {total_tasks} задач на языках: {', '.join(sorted(tasks_by_language.keys()))}",
            messages.INFO
        )
        self.message_user(request, "=" * 60, messages.INFO)
        
        published_count = 0
        errors = []
        published_by_language = {}
        published_tasks = []
        
        for task in all_related_tasks:
            try:
                # Получаем ВСЕ переводы задачи
                translations = task.translations.all()
                if not translations:
                    error_msg = f"Задача {task.id}: отсутствуют переводы"
                    errors.append(error_msg)
                    self.message_user(request, f"⚠️ {error_msg}", messages.WARNING)
                    logger.warning(f"Пропуск задачи {task.id}: нет переводов")
                    continue

                # Автоматическая генерация изображения, если его нет (используем логику из generate_images)
                if not task.image_url:
                    # Получаем первый перевод для генерации
                    first_translation = translations.first()
                    if not first_translation:
                        error_msg = f"Задача {task.id}: нет переводов для генерации изображения"
                        errors.append(error_msg)
                        self.message_user(request, f"❌ {error_msg}", messages.ERROR)
                        logger.error(f"Ошибка генерации изображения для задачи {task.id}: нет переводов")
                        continue

                    topic_name = task.topic.name if task.topic else 'python'
                    
                    self.message_user(
                        request,
                        f"🎨 Генерация изображения для задачи {task.id} (язык: {topic_name})...",
                        messages.INFO
                    )
                    logger.info(f"Генерация изображения для задачи {task.id} (язык: {topic_name})")
                    
                    try:
                        # Генерируем изображение (используем логику из generate_images)
                        image = generate_image_for_task(first_translation.question, topic_name)
                        
                        if image:
                            # Формируем имя файла в формате, как в боте (используем логику из generate_images)
                            language_code = first_translation.language or "unknown"
                            subtopic_name = task.subtopic.name if task.subtopic else 'general'
                            image_name = f"{task.topic.name}_{subtopic_name}_{language_code}_{task.id}.png"
                            image_name = image_name.replace(" ", "_").lower()
                            
                            self.message_user(request, f"☁️ Загрузка в S3: {image_name}...", messages.INFO)
                            
                            image_url = upload_image_to_s3(image, image_name)
                            
                            if image_url:
                                task.image_url = image_url
                                task.error = False  # Сбрасываем ошибку если генерация успешна
                                task.save(update_fields=['image_url', 'error'])
                                self.message_user(request, f"✅ Задача {task.id}: изображение загружено в S3", messages.SUCCESS)
                                self.message_user(request, f"   URL: {image_url}", messages.INFO)
                                logger.info(f"✅ Изображение успешно сгенерировано для задачи {task.id}")
                            else:
                                task.error = True
                                task.save(update_fields=['error'])
                                error_msg = f"Задача {task.id}: не удалось загрузить в S3"
                                errors.append(error_msg)
                                self.message_user(request, f"❌ {error_msg}", messages.ERROR)
                                continue
                        else:
                            task.error = True
                            task.save(update_fields=['error'])
                            error_msg = f"Задача {task.id}: не удалось сгенерировать изображение"
                            errors.append(error_msg)
                            self.message_user(request, f"❌ {error_msg}", messages.ERROR)
                            continue
                    except Exception as e:
                        task.error = True
                        task.save(update_fields=['error'])
                        error_msg = f"Задача {task.id}: {str(e)}"
                        errors.append(error_msg)
                        self.message_user(request, f"❌ {error_msg}", messages.ERROR)
                        logger.error(f"Исключение при генерации изображения для задачи {task.id}: {e}", exc_info=True)
                        continue

                # Публикуем каждый перевод в свой канал
                task_published_any_language = False
                for translation in translations:
                    language = translation.language.upper()

                    telegram_group = TelegramGroup.objects.filter(
                        topic_id=task.topic,
                        language=translation.language
                    ).first()

                    if not telegram_group:
                        error_msg = f"Задача {task.id} ({language}): не найдена Telegram группа для языка {language} (topic_id={task.topic.id if task.topic else None})"
                        errors.append(error_msg)
                        self.message_user(request, f"⚠️ {error_msg}", messages.WARNING)
                        logger.warning(f"Пропуск задачи {task.id} ({language}): не найдена TelegramGroup для topic_id={task.topic.id if task.topic else None}, language={translation.language}")
                        continue

                    self.message_user(
                        request,
                        f"🚀 Публикуем задачу {task.id} ({language}) в канал {telegram_group.group_name}...",
                        messages.INFO
                    )

                    result = publish_task_to_telegram(
                        task=task,
                        translation=translation,
                        telegram_group=telegram_group
                    )

                    if result.get('detailed_logs'):
                        for log in result['detailed_logs']:
                            if log.startswith('✅') or log.startswith('🎉'):
                                self.message_user(request, log, messages.SUCCESS)
                            elif log.startswith('🚀') or log.startswith('📷') or log.startswith('📝') or log.startswith('📊') or log.startswith('🔗'):
                                self.message_user(request, log, messages.INFO)
                            elif log.startswith('⚠️'):
                                self.message_user(request, log, messages.WARNING)
                            elif log.startswith('❌'):
                                self.message_user(request, log, messages.ERROR)
                            else:
                                self.message_user(request, log, messages.INFO)

                    if result['success']:
                        task_published_any_language = True
                        if language not in published_by_language:
                            published_by_language[language] = 0
                        published_by_language[language] += 1
                    else:
                        error_details = ', '.join(result['errors'])
                        errors.append(f"Задача {task.id} ({language}): {error_details}")
                        self.message_user(request, f"❌ Задача {task.id} ({language}): {error_details}", messages.ERROR)

                if task_published_any_language:
                    task.published = True
                    task.published_telegram = True
                    task.published_website = True
                    task.published_mini_app = True
                    task.publish_date = timezone.now()
                    task.error = False
                    update_fields = ['published', 'published_telegram', 'published_website', 'published_mini_app', 'publish_date', 'error']
                    if not task.message_id:
                        update_fields.append('message_id')
                    if not task.group:
                        update_fields.append('group')
                    task.save(update_fields=update_fields)
                    published_count += 1
                    published_tasks.append(task)
                else:
                    task.error = True
                    task.save(update_fields=['error'])
                    errors.append(f"Задача {task.id}: не удалось опубликовать ни один перевод")
                    self.message_user(request, f"❌ Задача {task.id}: не удалось опубликовать ни один перевод", messages.ERROR)

            except Exception as e:
                task.error = True
                task.save(update_fields=['error'])
                error_msg = f"Задача {task.id}: {str(e)}"
                errors.append(error_msg)
                self.message_user(request, f"❌ {error_msg}", messages.ERROR)
                logger.error(f"Исключение при публикации задачи {task.id}: {e}", exc_info=True)
            finally:
                self._pause_between_task_publications(request, task.id)
        
        # Итоговое сообщение
        self.message_user(request, "=" * 60, messages.INFO)

        if published_tasks:
            # Обновляем задачи из БД, чтобы подтянуть `TaskPoll`
            published_task_ids = [task.id for task in published_tasks]
            refreshed_tasks = list(Task.objects.filter(id__in=published_task_ids).prefetch_related('translations__taskpoll_set'))

            try:
                # Получаем admin_chat_id для уведомлений о результатах
                admin_chat_id = None
                try:
                    from accounts.models import TelegramAdmin
                    admin = TelegramAdmin.objects.filter(is_active=True).first()
                    if admin:
                        admin_chat_id = str(admin.telegram_id)
                except Exception:
                    pass  # Не критично, если не найдется

                # Анализируем активные вебхуки для определения стратегии генерации видео
                from webhooks.models import Webhook
                from config.tasks import generate_video_for_task_async

                active_webhooks = list(Webhook.objects.filter(is_active=True))
                webhook_types = set(webhook.webhook_type for webhook in active_webhooks)

                # Определяем стратегию генерации видео
                needs_video_generation = bool(webhook_types.intersection({'russian_only', 'english_only'}))

                if not active_webhooks:
                    # Нет активных вебхуков - просто публикуем без генерации видео
                    self.message_user(
                        request,
                        f"✅ Задачи опубликованы. Нет активных вебхуков - генерация видео пропущена",
                        messages.SUCCESS
                    )
                elif not needs_video_generation:
                    # Только regular вебхуки - отправляем без видео
                    from config.tasks import send_webhooks_async
                    webhook_task = send_webhooks_async.delay(
                        task_ids=[task.id for task in refreshed_tasks],
                        webhook_type_filter=None,
                        admin_chat_id=admin_chat_id,
                        include_video=False
                    )
                    self.message_user(
                        request,
                        f"🛰️ Regular вебхуки отправлены без видео (ID: {webhook_task.id})",
                        messages.SUCCESS
                    )
                else:
                    # Есть языковые вебхуки - генерируем видео для нужных языков
                    languages_to_generate = set()

                    if 'russian_only' in webhook_types:
                        languages_to_generate.add('ru')
                    if 'english_only' in webhook_types:
                        languages_to_generate.add('en')

                    # Генерируем видео для каждого нужного языка
                    for task in refreshed_tasks:
                        # Отмечаем какие языки планируются к генерации
                        task.video_generation_progress = {lang: False for lang in languages_to_generate}
                        task.save(update_fields=['video_generation_progress'])

                        for language in languages_to_generate:
                            translation = task.translations.filter(language=language).first()
                            if translation:
                                # Запускаем генерацию видео для этого языка
                                generate_video_for_task_async.delay(
                                    task_id=task.id,
                                    task_question=translation.question,
                                    topic_name=task.topic.name,
                                    subtopic_name=task.subtopic.name if task.subtopic else None,
                                    difficulty=task.difficulty,
                                    admin_chat_id=admin_chat_id,
                                    video_language=language,  # Передаем язык для видео
                                    expected_languages=list(languages_to_generate)  # Передаем все ожидаемые языки как список
                                )

                    video_count = len(refreshed_tasks) * len(languages_to_generate)
                    self.message_user(
                        request,
                        f"🎬 Запущена генерация {video_count} видео для языков: {', '.join(languages_to_generate)}",
                        messages.SUCCESS
                    )
                    self.message_user(
                        request,
                        f"🛰️ Вебхуки будут отправлены с видео после завершения генерации",
                        messages.INFO
                    )

                if admin_chat_id:
                    self.message_user(
                        request,
                        "📨 Результаты будут отправлены в Telegram",
                        messages.INFO
                    )
                else:
                    self.message_user(
                        request,
                        "ℹ️ Настройте Telegram админа для получения уведомлений о результатах",
                        messages.WARNING
                    )

            except Exception as exc:
                logger.exception("Ошибка при отправке сводного вебхука: %s", exc)
                self.message_user(
                    request,
                    f"❌ Ошибка при отправке сводного вебхука: {exc}",
                    messages.ERROR
                )

        if published_count > 0:
            # Формируем информацию по языкам
            lang_stats = ", ".join([f"{lang}: {count}" for lang, count in sorted(published_by_language.items())])
            
            self.message_user(
                request,
                f"🎉 УСПЕШНО: Опубликовано {published_count} задач из {total_tasks}",
                messages.SUCCESS
            )
            self.message_user(
                request,
                f"📊 По языкам: {lang_stats}",
                messages.SUCCESS
            )
        
        if errors:
            self.message_user(
                request,
                f"⚠️ Ошибок: {len(errors)} из {total_tasks}",
                messages.WARNING
            )
    
    @admin.action(description='Сгенерировать изображения для выбранных задач')
    def generate_images(self, request, queryset):
        """
        Генерирует и загружает изображения для задач с детальными логами.
        """
        generated_count = 0
        skipped_count = 0
        errors = []
        total_tasks = queryset.count()
        
        self.message_user(request, f"📊 Начинаем генерацию изображений для {total_tasks} задач...", messages.INFO)
        
        for task in queryset:
            if task.image_url:
                skipped_count += 1
                self.message_user(request, f"⏭️ Задача {task.id}: изображение уже существует", messages.INFO)
                continue
            
            # Получаем первый перевод для генерации
            translation = task.translations.first()
            if not translation:
                error_msg = f"Задача {task.id}: отсутствуют переводы"
                errors.append(error_msg)
                self.message_user(request, f"⚠️ {error_msg}", messages.WARNING)
                continue
            
            try:
                topic_name = task.topic.name if task.topic else 'python'
                
                self.message_user(request, f"🎨 Генерация изображения для задачи {task.id} (язык: {topic_name})...", messages.INFO)
                
                # Генерируем изображение
                image = generate_image_for_task(translation.question, topic_name)
                
                if image:
                    # Формируем имя файла в формате, как в боте
                    language_code = translation.language or "unknown"
                    subtopic_name = task.subtopic.name if task.subtopic else 'general'
                    image_name = f"{task.topic.name}_{subtopic_name}_{language_code}_{task.id}.png"
                    image_name = image_name.replace(" ", "_").lower()
                    
                    self.message_user(request, f"☁️ Загрузка в S3: {image_name}...", messages.INFO)
                    
                    image_url = upload_image_to_s3(image, image_name)
                    
                    if image_url:
                        task.image_url = image_url
                        task.error = False  # Сбрасываем ошибку если генерация успешна
                        task.save(update_fields=['image_url', 'error'])
                        generated_count += 1
                        self.message_user(request, f"✅ Задача {task.id}: изображение загружено в S3", messages.SUCCESS)
                        self.message_user(request, f"   URL: {image_url}", messages.INFO)
                    else:
                        task.error = True
                        task.save(update_fields=['error'])
                        error_msg = f"Задача {task.id}: не удалось загрузить в S3"
                        errors.append(error_msg)
                        self.message_user(request, f"❌ {error_msg}", messages.ERROR)
                else:
                    task.error = True
                    task.save(update_fields=['error'])
                    error_msg = f"Задача {task.id}: не удалось сгенерировать изображение"
                    errors.append(error_msg)
                    self.message_user(request, f"❌ {error_msg}", messages.ERROR)
            except Exception as e:
                task.error = True
                task.save(update_fields=['error'])
                error_msg = f"Задача {task.id}: {str(e)}"
                errors.append(error_msg)
                self.message_user(request, f"❌ {error_msg}", messages.ERROR)
        
        # Итоговое сообщение
        self.message_user(request, "=" * 60, messages.INFO)
        self.message_user(request, f"🎉 ЗАВЕРШЕНО: Сгенерировано {generated_count}, пропущено {skipped_count}, ошибок {len(errors)}", messages.SUCCESS if generated_count > 0 else messages.INFO)
    
    @admin.action(description='🎬 Сгенерировать видео')
    def generate_videos(self, request, queryset):
        """
        Генерирует видео для выбранных задач.
        Каждая задача имеет один перевод, поэтому генерируется одно видео на задачу.
        """
        from config.tasks import generate_video_for_task_async

        generated_count = 0
        skipped_count = 0
        errors = []
        total_tasks = queryset.count()

        # Получаем admin_chat_id для отправки видео админу
        from django.conf import settings
        admin_chat_id = getattr(settings, 'TELEGRAM_ADMIN_CHAT_ID', None)

        if not admin_chat_id:
            try:
                from accounts.models import TelegramAdmin
                admin = TelegramAdmin.objects.filter(is_active=True).first()
                if admin:
                    admin_chat_id = str(admin.telegram_id)
            except Exception as e:
                logger.warning(f"⚠️ Не удалось получить chat_id админа: {e}")

        self.message_user(request, f"📊 Генерация видео для {total_tasks} выбранных задач...", messages.INFO)

        for task in queryset:
            # Каждая задача имеет только один перевод
            translation = task.translations.first()
            if not translation:
                error_msg = f"Задача {task.id}: отсутствует перевод"
                errors.append(error_msg)
                self.message_user(request, f"⚠️ {error_msg}", messages.WARNING)
                skipped_count += 1
                continue

            language = translation.language
            self.message_user(request, f"🎬 Задача {task.id} ({language}): генерация видео...", messages.INFO)

            try:
                # Получаем информацию о теме и подтеме
                topic_name = task.topic.name if task.topic else 'unknown'
                subtopic_name = task.subtopic.name if task.subtopic else None
                difficulty = task.difficulty if hasattr(task, 'difficulty') else None

                # Очищаем логи
                task.video_generation_logs = None
                task.video_generation_progress = {language: False}
                task.save(update_fields=['video_generation_logs', 'video_generation_progress'])

                # Запускаем генерацию видео
                celery_task = generate_video_for_task_async.delay(
                    task_id=task.id,
                    task_question=translation.question,
                    topic_name=topic_name,
                    subtopic_name=subtopic_name,
                    difficulty=difficulty,
                    force_regenerate=True,
                    admin_chat_id=admin_chat_id,
                    video_language=language,
                    expected_languages=[language]
                )

                generated_count += 1
                self.message_user(request, f"✅ Задача {task.id} ({language}): генерация запущена (Celery task: {celery_task.id})", messages.SUCCESS)

            except Exception as e:
                error_msg = f"Задача {task.id}: {str(e)}"
                errors.append(error_msg)
                self.message_user(request, f"❌ {error_msg}", messages.ERROR)

        self.message_user(request, "=" * 60, messages.INFO)
        self.message_user(request, f"🎉 Готово: {generated_count} генераций запущено, {skipped_count} пропущено, {len(errors)} ошибок", messages.SUCCESS if generated_count > 0 else messages.INFO)
    
    @admin.action(description='📱 Опубликовать во все соцсети')
    def publish_to_all_social_networks(self, request, queryset):
        """
        Публикует выбранные задачи во все активные социальные сети.
        Работает через API (Pinterest, Дзен, Facebook) и webhook (Instagram, TikTok, YouTube).
        """
        from .services.social_media_service import publish_to_social_media
        
        total_tasks = queryset.count()
        published_tasks = 0
        
        self.message_user(
            request,
            f"📊 Начинаем публикацию {total_tasks} задач во все социальные сети...",
            messages.INFO
        )
        
        for task in queryset:
            try:
                # Проверяем наличие изображения
                if not task.image_url:
                    self.message_user(
                        request,
                        f"⚠️ Задача {task.id}: нет изображения, пропускаем",
                        messages.WARNING
                    )
                    continue
                
                # Получаем перевод
                translation = task.translations.first()
                if not translation:
                    self.message_user(
                        request,
                        f"⚠️ Задача {task.id}: нет переводов, пропускаем",
                        messages.WARNING
                    )
                    continue
                
                # Публикуем
                result = publish_to_social_media(task, translation)
                
                if result['success'] > 0:
                    published_tasks += 1
                    # Обновляем статус задачи
                    task.published = True
                    if not task.publish_date:
                        task.publish_date = timezone.now()
                    task.save(update_fields=['published', 'publish_date'])

                    self.message_user(
                        request,
                        f"✅ Задача {task.id}: опубликовано в {result['success']}/{result['total']} платформ",
                        messages.SUCCESS
                    )
                else:
                    self.message_user(
                        request,
                        f"❌ Задача {task.id}: не удалось опубликовать ни в одной платформе",
                        messages.ERROR
                    )
                
            except Exception as e:
                logger.error(f"Ошибка публикации задачи {task.id}: {e}", exc_info=True)
                self.message_user(
                    request,
                    f"❌ Задача {task.id}: ошибка - {str(e)}",
                    messages.ERROR
                )
        
        # Итоговое сообщение
        self.message_user(
            request,
            f"🎉 Готово! Опубликовано {published_tasks} из {total_tasks} задач",
            messages.SUCCESS if published_tasks > 0 else messages.WARNING
        )
    
    def _publish_to_platform_action(self, request, queryset, platform: str, platform_name: str):
        """
        Вспомогательная функция для публикации в конкретную платформу.
        """
        from .services.social_media_service import publish_to_platform
        
        total_tasks = queryset.count()
        published_tasks = 0
        
        self.message_user(
            request,
            f"📊 Начинаем публикацию {total_tasks} задач в {platform_name}...",
            messages.INFO
        )
        
        for task in queryset:
            try:
                # Проверяем наличие изображения
                if not task.image_url:
                    self.message_user(
                        request,
                        f"⚠️ Задача {task.id}: нет изображения, пропускаем",
                        messages.WARNING
                    )
                    continue
                
                # Получаем перевод
                translation = task.translations.first()
                if not translation:
                    self.message_user(
                        request,
                        f"⚠️ Задача {task.id}: нет переводов, пропускаем",
                        messages.WARNING
                    )
                    continue
                
                # Публикуем в конкретную платформу
                result = publish_to_platform(task, translation, platform)
                
                if result.get('success'):
                    published_tasks += 1
                    # Обновляем статус задачи
                    task.published = True
                    if not task.publish_date:
                        task.publish_date = timezone.now()
                    task.save(update_fields=['published', 'publish_date'])

                    status = result.get('status', 'published')
                    if status == 'already_published':
                        self.message_user(
                            request,
                            f"ℹ️ Задача {task.id}: уже опубликована в {platform_name}",
                            messages.INFO
                        )
                    elif status == 'sent_to_webhook':
                        self.message_user(
                            request,
                            f"✅ Задача {task.id}: отправлена в {platform_name} через webhook",
                            messages.SUCCESS
                        )
                    else:
                        post_url = result.get('post_url', '')
                        self.message_user(
                            request,
                            f"✅ Задача {task.id}: опубликована в {platform_name}" + (f" - {post_url}" if post_url else ""),
                            messages.SUCCESS
                        )
                else:
                    error = result.get('error', 'Неизвестная ошибка')
                    self.message_user(
                        request,
                        f"❌ Задача {task.id}: ошибка публикации в {platform_name} - {error}",
                        messages.ERROR
                    )
                    
            except Exception as e:
                logger.error(f"Ошибка публикации задачи {task.id} в {platform_name}: {e}", exc_info=True)
                self.message_user(
                    request,
                    f"❌ Задача {task.id}: ошибка публикации в {platform_name} - {str(e)}",
                    messages.ERROR
                )
        
        self.message_user(
            request,
            f"📊 Публикация в {platform_name} завершена: {published_tasks}/{total_tasks} задач опубликовано",
            messages.SUCCESS if published_tasks > 0 else messages.WARNING
        )
    
    @admin.action(description='📌 Опубликовать в Pinterest')
    def publish_to_pinterest(self, request, queryset):
        """Публикует выбранные задачи в Pinterest."""
        self._publish_to_platform_action(request, queryset, 'pinterest', 'Pinterest')
    
    @admin.action(description='👤 Опубликовать в Facebook')
    def publish_to_facebook(self, request, queryset):
        """Публикует выбранные задачи в Facebook."""
        self._publish_to_platform_action(request, queryset, 'facebook', 'Facebook')
    
    @admin.action(description='📰 Опубликовать в Яндекс Дзен')
    def publish_to_yandex_dzen(self, request, queryset):
        """Публикует выбранные задачи в Яндекс Дзен."""
        self._publish_to_platform_action(request, queryset, 'yandex_dzen', 'Яндекс Дзен')
    
    @admin.action(description='📸 Опубликовать в Instagram')
    def publish_to_instagram(self, request, queryset):
        """Публикует выбранные задачи в Instagram через webhook."""
        self._publish_to_platform_action(request, queryset, 'instagram', 'Instagram')
    
    @admin.action(description='🎵 Опубликовать в TikTok')
    def publish_to_tiktok(self, request, queryset):
        """Публикует выбранные задачи в TikTok через webhook."""
        self._publish_to_platform_action(request, queryset, 'tiktok', 'TikTok')
    
    @admin.action(description='🎬 Опубликовать в YouTube Shorts')
    def publish_to_youtube_shorts(self, request, queryset):
        """Публикует выбранные задачи в YouTube Shorts через webhook."""
        self._publish_to_platform_action(request, queryset, 'youtube_shorts', 'YouTube Shorts')
    
    @admin.action(description='🎥 Опубликовать в Instagram Reels')
    def publish_to_instagram_reels(self, request, queryset):
        """Публикует выбранные задачи в Instagram Reels через браузерную автоматизацию."""
        self._publish_to_platform_action(request, queryset, 'instagram_reels', 'Instagram Reels')
    
    @admin.action(description='📸 Опубликовать в Instagram Stories')
    def publish_to_instagram_stories(self, request, queryset):
        """Публикует выбранные задачи в Instagram Stories через браузерную автоматизацию."""
        self._publish_to_platform_action(request, queryset, 'instagram_stories', 'Instagram Stories')
    
    @admin.action(description='👤 Опубликовать в Facebook Stories')
    def publish_to_facebook_stories(self, request, queryset):
        """Публикует выбранные задачи в Facebook Stories через браузерную автоматизацию."""
        self._publish_to_platform_action(request, queryset, 'facebook_stories', 'Facebook Stories')
    
    @admin.action(description='🎬 Опубликовать в Facebook Reels')
    def publish_to_facebook_reels(self, request, queryset):
        """Публикует выбранные задачи в Facebook Reels через браузерную автоматизацию."""
        self._publish_to_platform_action(request, queryset, 'facebook_reels', 'Facebook Reels')
    
    @admin.action(description='🚀 Опубликовать Reels с автоматическим репостом')
    def publish_with_auto_reshare(self, request, queryset):
        """
        Публикует Reels в Instagram с автоматическим кросспостингом в Facebook и добавлением в Stories.
        """
        from .services.social_media_service import publish_to_platform
        
        total_tasks = queryset.count()
        published_tasks = 0
        
        self.message_user(
            request,
            f"📊 Начинаем публикацию {total_tasks} задач в Instagram Reels с автоматическим репостом...",
            messages.INFO
        )
        
        for task in queryset:
            try:
                # Проверяем наличие видео
                if not task.video_url:
                    self.message_user(
                        request,
                        f"⚠️ Задача {task.id}: нет видео, пропускаем",
                        messages.WARNING
                    )
                    continue
                
                # Получаем перевод
                translation = task.translations.first()
                if not translation:
                    self.message_user(
                        request,
                        f"⚠️ Задача {task.id}: нет переводов, пропускаем",
                        messages.WARNING
                    )
                    continue
                
                # Публикуем в Instagram Reels (с автоматическим кросспостингом)
                result = publish_to_platform(task, translation, 'instagram_reels')
                
                if result.get('success'):
                    published_tasks += 1
                    # Обновляем статус задачи
                    task.published = True
                    if not task.publish_date:
                        task.publish_date = timezone.now()
                    task.save(update_fields=['published', 'publish_date'])
                    post_url = result.get('post_url', '')
                    facebook_id = result.get('facebook_post_id')
                    story_id = result.get('instagram_story_id')
                    
                    msg = f"✅ Задача {task.id}: опубликована в Instagram Reels"
                    if post_url:
                        msg += f" - {post_url}"
                    if facebook_id:
                        msg += f" | Facebook Reels: {facebook_id}"
                    if story_id:
                        msg += f" | Instagram Story: {story_id}"
                    
                    self.message_user(request, msg, messages.SUCCESS)
                else:
                    error = result.get('error', 'Неизвестная ошибка')
                    self.message_user(
                        request,
                        f"❌ Задача {task.id}: ошибка - {error}",
                        messages.ERROR
                    )
                    
            except Exception as e:
                logger.error(f"Ошибка публикации задачи {task.id}: {e}", exc_info=True)
                self.message_user(
                    request,
                    f"❌ Задача {task.id}: ошибка - {str(e)[:100]}",
                    messages.ERROR
                )
        
        self.message_user(
            request,
            f"🎉 Готово! Опубликовано {published_tasks} из {total_tasks} задач",
            messages.SUCCESS if published_tasks > 0 else messages.WARNING
        )
    
    @admin.action(description='Снять флаг ошибки')
    def clear_error_flag(self, request, queryset):
        """
        Снимает флаг ошибки (error = False) для выбранных задач.
        Полезно когда ошибка исправлена или была ложной.
        """
        # Собираем все translation_group_id
        translation_group_ids = set(
            queryset.values_list('translation_group_id', flat=True)
        )
        
        # Находим все связанные задачи
        all_related_tasks = Task.objects.filter(
            translation_group_id__in=translation_group_ids
        )
        
        # Подсчитываем по языкам
        languages = []
        for task in all_related_tasks:
            translation = task.translations.first()
            if translation:
                languages.append(translation.language.upper())
        
        # Сбрасываем флаг ошибки для всех связанных задач
        updated_count = all_related_tasks.update(error=False)
        
        lang_info = ", ".join(sorted(set(languages))) if languages else ""
        
        self.message_user(
            request,
            f"✅ Флаг ошибки сброшен для {updated_count} задач ({lang_info})",
            messages.SUCCESS
        )

    def send_webhooks_separately(self, request, queryset):
        """
        Отправляет выбранные задачи только на вебхуки (без публикации в соцсети).
        Следует новой логике: проверяет активные вебхуки, генерирует видео только для нужных языков,
        отправляет вебхуки с видео после завершения генерации.
        """
        from config.tasks import send_webhooks_async, generate_video_for_task_async

        # Собираем все translation_group_id
        translation_group_ids = set(
            queryset.values_list('translation_group_id', flat=True)
        )

        # Находим все связанные задачи
        all_related_tasks = Task.objects.filter(
            translation_group_id__in=translation_group_ids
        ).select_related('topic', 'subtopic', 'group').prefetch_related('translations')

        # Группируем задачи по языкам для информирования
        tasks_by_language = {}
        for task in all_related_tasks:
            translation = task.translations.first()
            if translation:
                lang = translation.language.upper()
                if lang not in tasks_by_language:
                    tasks_by_language[lang] = []
                tasks_by_language[lang].append(task)

        total_tasks = all_related_tasks.count()
        selected_count = queryset.count()

        # Информируем пользователя о масштабе операции
        self.message_user(
            request,
            f"📊 Выбрано задач: {selected_count}",
            messages.INFO
        )
        self.message_user(
            request,
            f"🌍 Найдено связанных переводов: {total_tasks} задач на языках: {', '.join(sorted(tasks_by_language.keys()))}",
            messages.INFO
        )

        # Анализируем активные вебхуки для определения стратегии
        from webhooks.models import Webhook
        active_webhooks = list(Webhook.objects.filter(is_active=True))
        webhook_types = set(webhook.webhook_type for webhook in active_webhooks)

        # Определяем стратегию генерации видео
        # Видео генерируется только если есть языковые вебхуки (russian_only, english_only)
        needs_video_generation = bool(webhook_types.intersection({'russian_only', 'english_only'}))

        # Логируем для отладки
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"send_webhooks_separately: Активных вебхуков: {len(active_webhooks)}")
        logger.info(f"send_webhooks_separately: Типы вебхуков: {webhook_types}")
        logger.info(f"send_webhooks_separately: Нужна генерация видео: {needs_video_generation}")

        try:
            # Получаем admin_chat_id для уведомлений
            admin_chat_id = None
            try:
                from accounts.models import TelegramAdmin
                admin = TelegramAdmin.objects.filter(is_active=True).first()
                if admin:
                    admin_chat_id = str(admin.telegram_id)
                    logger.info(f"send_webhooks_separately: Найден admin_chat_id: {admin_chat_id}")
                else:
                    logger.warning("send_webhooks_separately: TelegramAdmin не найден")
            except Exception as e:
                logger.error(f"send_webhooks_separately: Ошибка при поиске admin_chat_id: {e}")
                pass  # Не критично, если не найдется

            if not active_webhooks:
                # Нет активных вебхуков - просто сообщаем
                logger.info("send_webhooks_separately: Нет активных вебхуков")
                self.message_user(
                    request,
                    f"⚠️ Нет активных вебхуков для отправки",
                    messages.WARNING
                )
                return

            elif not needs_video_generation:
                # Только regular вебхуки - отправляем без видео
                logger.info("send_webhooks_separately: Запуск отправки regular вебхуков без видео")
                webhook_task = send_webhooks_async.delay(
                    task_ids=[task.id for task in all_related_tasks],
                    webhook_type_filter=None,
                    admin_chat_id=admin_chat_id,
                    include_video=False
                )
                logger.info(f"send_webhooks_separately: Regular вебхуки запущены (ID: {webhook_task.id})")
                self.message_user(
                    request,
                    f"🛰️ Regular вебхуки отправлены без видео (ID: {webhook_task.id})",
                    messages.SUCCESS
                )

            else:
                # Есть языковые вебхуки - генерируем видео для нужных языков
                logger.info("send_webhooks_separately: Запуск генерации видео для языковых вебхуков")
                languages_to_generate = set()

                if 'russian_only' in webhook_types:
                    languages_to_generate.add('ru')
                if 'english_only' in webhook_types:
                    languages_to_generate.add('en')

                logger.info(f"send_webhooks_separately: Языки для генерации: {languages_to_generate}")

                # Генерируем видео для каждого нужного языка
                for task in all_related_tasks:
                    for language in languages_to_generate:
                        translation = task.translations.filter(language=language).first()
                        if translation:
                            # Запускаем генерацию видео для этого языка
                            generate_video_for_task_async.delay(
                                task_id=task.id,
                                task_question=translation.question,
                                topic_name=task.topic.name,
                                subtopic_name=task.subtopic.name if task.subtopic else None,
                                difficulty=task.difficulty,
                                admin_chat_id=admin_chat_id,
                                video_language=language,  # Передаем язык для видео
                                expected_languages=list(languages_to_generate)  # Передаем все ожидаемые языки как список
                            )

                video_count = len(all_related_tasks) * len(languages_to_generate)
                self.message_user(
                    request,
                    f"🎬 Запущена генерация {video_count} видео для языков: {', '.join(languages_to_generate)}",
                    messages.SUCCESS
                )
                self.message_user(
                    request,
                    f"🛰️ Вебхуки будут отправлены с видео после завершения генерации",
                    messages.INFO
                )

            if admin_chat_id:
                self.message_user(
                    request,
                    "📨 Подробные результаты будут отправлены в Telegram",
                    messages.INFO
                )
            else:
                self.message_user(
                    request,
                    "📋 Результаты будут доступны в логах Celery",
                    messages.INFO
                )

            self.message_user(request, "=" * 60, messages.INFO)

        except Exception as e:
            self.message_user(
                request,
                f"❌ Ошибка при запуске задачи Celery: {str(e)}",
                messages.ERROR
            )
            logger.error(f"Ошибка запуска Celery задачи для вебхуков: {e}")

    send_webhooks_separately.short_description = "🛰️ Отправить вебхуки с видео"


@admin.register(BackgroundMusic)
class BackgroundMusicAdmin(TenantFilteredAdminMixin, admin.ModelAdmin):
    """Админка для управления фоновыми треками."""
    list_display = ('id', 'name', 'duration_seconds', 'display_size', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name',)
    readonly_fields = ('audio_preview', 'created_at', 'updated_at')
    fields = ('name', 'audio_file', 'audio_preview', 'is_active', 'created_at', 'updated_at')
    actions = ['make_active', 'make_inactive', 'delete_selected_tracks']

    def display_size(self, obj):
        if not obj.size:
            return '—'
        # Читаемый формат
        size = int(obj.size)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size}{unit}"
            size = size // 1024
        return f"{size}TB"
    display_size.short_description = 'Размер'

    def audio_preview(self, obj):
        if not obj.audio_file:
            return '—'
        try:
            url = obj.audio_file.url
            return format_html('<audio controls style="width: 300px;"><source src="{}"></audio>', url)
        except Exception:
            return '—'
    audio_preview.short_description = 'Превью'

    def make_active(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"✅ Активировано треков: {updated}")
    make_active.short_description = 'Активировать выбранные треки'

    def make_inactive(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"✅ Деактивировано треков: {updated}")
    make_inactive.short_description = 'Деактивировать выбранные треки'

    def delete_selected_tracks(self, request, queryset):
        """
        Удаляет выбранные треки из базы и удаляет файл из связанного storage.
        Сообщает об успехах и неудачах через Django messages.
        """
        deleted = 0
        failed = []
        for obj in queryset:
            try:
                # Пытаемся удалить файл через FileField storage
                try:
                    if getattr(obj, 'audio_file', None):
                        try:
                            obj.audio_file.delete(save=False)
                            logger.info(f"Удалён файл аудио для трека {obj.id}: {obj.audio_file.name}")
                        except Exception as e_file:
                            # Логируем и продолжаем попытку удалить объект
                            logger.warning(f"Не удалось удалить файл аудио для трека {obj.id}: {e_file}")
                except Exception:
                    # Если у объекта нет audio_file или другой неожиданный кейс, продолжаем
                    pass

                # Удаляем сам объект из БД
                obj.delete()
                deleted += 1
            except Exception as e:
                logger.error(f"Ошибка при удалении трека {getattr(obj, 'id', '<unknown>')}: {e}")
                failed.append(str(getattr(obj, 'id', '<unknown>')))

        if deleted:
            self.message_user(request, f"🗑️ Удалено треков: {deleted}", messages.SUCCESS)
        if failed:
            self.message_user(request, f"⚠️ Не удалось удалить треки с ID: {', '.join(failed)}", messages.WARNING)
    delete_selected_tracks.short_description = '🗑️ Удалить выбранные треки (файл будет удалён из storage)'


@admin.register(TaskCommentReport)
class TaskCommentReportAdmin(TenantFilteredAdminMixin, admin.ModelAdmin):
    tenant_lookup = 'comment__task__tenant'
    """Админка для управления жалобами на комментарии."""
    list_display = ('id', 'comment_author_info', 'reporter_info', 'reason', 'is_reviewed', 'created_at', 'ban_user_buttons')
    list_filter = ('reason', 'is_reviewed', 'created_at')
    search_fields = ('comment__text', 'reporter_telegram_id', 'comment__author_telegram_id', 'comment__author_username')
    readonly_fields = ('comment_link', 'comment_author_info', 'reporter_info', 'comment_text_preview', 'ban_user_buttons', 'created_at')
    fields = (
        'comment_link',
        'comment_author_info',
        'reporter_info',
        'reason',
        'description',
        'comment_text_preview',
        'is_reviewed',
        'ban_user_buttons',
        'created_at'
    )
    actions = ['mark_as_reviewed', 'mark_as_unreviewed', 'ban_author_1_hour', 'ban_author_24_hours', 'ban_author_7_days', 'ban_author_permanent', 'unban_author']
    
    def comment_link(self, obj):
        """Ссылка на комментарий."""
        if obj.comment:
            try:
                comment_url = reverse('admin:tasks_taskcomment_change', args=[obj.comment.id])
            except Exception:
                comment_url = f"/admin/tasks/taskcomment/{obj.comment.id}/change/"
            return format_html('<a href="{}">Комментарий #{}</a>', comment_url, obj.comment.id)
        return '-'
    comment_link.short_description = 'Комментарий'
    
    def comment_author_info(self, obj):
        """Информация об авторе комментария."""
        if not obj.comment:
            return '-'
        
        author_id = obj.comment.author_telegram_id
        author_username = obj.comment.author_username or 'нет'
        
        # Пытаемся получить информацию из MiniAppUser
        try:
            from accounts.models import MiniAppUser
            author_user = MiniAppUser.objects.filter(telegram_id=author_id).first()
            if author_user:
                username = author_user.username or 'нет'
                name = author_user.first_name or author_user.username or 'Без имени'
                is_banned = author_user.is_banned
                banned_status = '🚫 Заблокирован' if is_banned else '✅ Активен'
                
                try:
                    user_url = reverse('admin:accounts_miniappuser_change', args=[author_user.id])
                except Exception:
                    user_url = f"/admin/accounts/miniappuser/{author_user.id}/change/"
                return format_html(
                    '<a href="{}">{} (@{})</a><br>ID: {}<br>Статус: {}',
                    user_url, name, username, author_id, banned_status
                )
        except Exception:
            pass
        
        return format_html('@{}<br>ID: {}', author_username, author_id)
    comment_author_info.short_description = 'Автор комментария'
    
    def reporter_info(self, obj):
        """Информация о пользователе, который подал жалобу."""
        reporter_id = obj.reporter_telegram_id
        
        # Пытаемся получить информацию из MiniAppUser
        try:
            from accounts.models import MiniAppUser
            reporter_user = MiniAppUser.objects.filter(telegram_id=reporter_id).first()
            if reporter_user:
                username = reporter_user.username or 'нет'
                name = reporter_user.first_name or reporter_user.username or 'Без имени'
                
                try:
                    user_url = reverse('admin:accounts_miniappuser_change', args=[reporter_user.id])
                except Exception:
                    user_url = f"/admin/accounts/miniappuser/{reporter_user.id}/change/"
                return format_html(
                    '<a href="{}">{} (@{})</a><br>ID: {}',
                    user_url, name, username, reporter_id
                )
        except Exception:
            pass
        
        return format_html('ID: {}', reporter_id)
    reporter_info.short_description = 'Подавший жалобу'
    
    def comment_text_preview(self, obj):
        """Превью текста комментария."""
        if obj.comment and obj.comment.text:
            text = obj.comment.text[:200] + ('...' if len(obj.comment.text) > 200 else '')
            return format_html('<div style="max-width: 500px; word-wrap: break-word;">{}</div>', text)
        return '-'
    comment_text_preview.short_description = 'Текст комментария'
    
    def ban_user_buttons(self, obj):
        """Кнопки для блокировки пользователя прямо из интерфейса жалобы (использует существующую логику из MiniAppUser)."""
        if not obj.comment:
            return '-'
        
        author_id = obj.comment.author_telegram_id
        
        # Пытаемся получить информацию из MiniAppUser
        try:
            from accounts.models import MiniAppUser
            author_user = MiniAppUser.objects.filter(telegram_id=author_id).first()
            if author_user:
                try:
                    user_url = reverse('admin:accounts_miniappuser_change', args=[author_user.id])
                except Exception:
                    user_url = f"/admin/accounts/miniappuser/{author_user.id}/change/"
                
                is_banned = author_user.is_banned
                status_text = '🚫 Заблокирован' if is_banned else '✅ Активен'
                
                # URL для блокировки/разблокировки
                try:
                    ban_1h_url = reverse('admin:tasks_taskcommentreport_ban_user', args=[obj.id, 1])
                    ban_24h_url = reverse('admin:tasks_taskcommentreport_ban_user', args=[obj.id, 24])
                    ban_7d_url = reverse('admin:tasks_taskcommentreport_ban_user', args=[obj.id, 168])
                    ban_permanent_url = reverse('admin:tasks_taskcommentreport_ban_user', args=[obj.id, 0])
                    unban_url = reverse('admin:tasks_taskcommentreport_unban_user', args=[obj.id])
                except Exception:
                    ban_1h_url = f"/admin/tasks/taskcommentreport/{obj.id}/ban/1/"
                    ban_24h_url = f"/admin/tasks/taskcommentreport/{obj.id}/ban/24/"
                    ban_7d_url = f"/admin/tasks/taskcommentreport/{obj.id}/ban/168/"
                    ban_permanent_url = f"/admin/tasks/taskcommentreport/{obj.id}/ban/0/"
                    unban_url = f"/admin/tasks/taskcommentreport/{obj.id}/unban/"
                
                if is_banned:
                    # Если пользователь уже заблокирован, показываем кнопку разблокировки
                    return format_html(
                        '<div style="margin: 10px 0; padding: 15px; background-color: #fff3cd; border: 1px solid #ffc107; border-radius: 5px;">'
                        '<p style="margin: 0 0 10px 0;"><strong>Статус:</strong> {}</p>'
                        '<a href="{}" class="button" style="background-color: #28a745; color: white; padding: 8px 15px; text-decoration: none; border-radius: 3px; display: inline-block; margin-right: 10px;">'
                        '✅ Разблокировать пользователя'
                        '</a>'
                        '<a href="{}" class="button" style="background-color: #007cba; color: white; padding: 8px 15px; text-decoration: none; border-radius: 3px; display: inline-block;">'
                        '👤 Перейти к профилю'
                        '</a>'
                        '</div>',
                        status_text, unban_url, user_url
                    )
                else:
                    # Если пользователь не заблокирован, показываем кнопки блокировки
                    return format_html(
                        '<div style="margin: 10px 0; padding: 15px; background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 5px;">'
                        '<p style="margin: 0 0 10px 0;"><strong>Статус:</strong> {}</p>'
                        '<div style="margin-bottom: 10px;">'
                        '<a href="{}" class="button" style="background-color: #ffc107; color: black; padding: 6px 12px; text-decoration: none; border-radius: 3px; display: inline-block; margin-right: 5px; margin-bottom: 5px;">'
                        '🚫 1 час'
                        '</a>'
                        '<a href="{}" class="button" style="background-color: #fd7e14; color: white; padding: 6px 12px; text-decoration: none; border-radius: 3px; display: inline-block; margin-right: 5px; margin-bottom: 5px;">'
                        '🚫 24 часа'
                        '</a>'
                        '<a href="{}" class="button" style="background-color: #dc3545; color: white; padding: 6px 12px; text-decoration: none; border-radius: 3px; display: inline-block; margin-right: 5px; margin-bottom: 5px;">'
                        '🚫 7 дней'
                        '</a>'
                        '<a href="{}" class="button" style="background-color: #721c24; color: white; padding: 6px 12px; text-decoration: none; border-radius: 3px; display: inline-block; margin-bottom: 5px;">'
                        '🚫 Навсегда'
                        '</a>'
                        '</div>'
                        '<a href="{}" class="button" style="background-color: #007cba; color: white; padding: 6px 12px; text-decoration: none; border-radius: 3px; display: inline-block;">'
                        '👤 Перейти к профилю'
                        '</a>'
                        '</div>',
                        status_text, ban_1h_url, ban_24h_url, ban_7d_url, ban_permanent_url, user_url
                    )
        except Exception:
            pass
        
        return format_html(
            '<div style="margin: 10px 0; color: #666;">'
            'Пользователь с ID {} не найден в системе Mini App'
            '</div>',
            author_id
        )
    ban_user_buttons.short_description = 'Блокировка пользователя'
    
    @admin.action(description='✅ Отметить как проверенные')
    def mark_as_reviewed(self, request, queryset):
        """Отмечает жалобы как проверенные."""
        count = queryset.update(is_reviewed=True)
        self.message_user(request, f'Отмечено {count} жалоб как проверенные', messages.SUCCESS)
    
    @admin.action(description='🔄 Отметить как непроверенные')
    def mark_as_unreviewed(self, request, queryset):
        """Отмечает жалобы как непроверенные."""
        count = queryset.update(is_reviewed=False)
        self.message_user(request, f'Отмечено {count} жалоб как непроверенные', messages.SUCCESS)
    
    def get_admin_telegram_id(self, request):
        """
        Получает telegram_id администратора (используем ту же логику, что и в MiniAppUserAdmin).
        Пытается найти через связи с MiniAppUser, DjangoAdmin, TelegramAdmin.
        """
        admin_id = None
        
        try:
            # Сначала пробуем получить через linked_custom_user -> MiniAppUser
            if hasattr(request.user, 'mini_app_profile'):
                mini_app_user = request.user.mini_app_profile
                if mini_app_user:
                    admin_id = mini_app_user.telegram_id
            
            # Если не нашли, пробуем через DjangoAdmin
            if not admin_id:
                from accounts.models import DjangoAdmin
                try:
                    django_admin = DjangoAdmin.objects.get(username=request.user.username)
                    if django_admin and hasattr(django_admin, 'mini_app_user') and django_admin.mini_app_user:
                        admin_id = django_admin.mini_app_user.telegram_id
                except DjangoAdmin.DoesNotExist:
                    pass
            
            # Если всё ещё не нашли, пробуем через TelegramAdmin
            if not admin_id:
                from accounts.models import TelegramAdmin
                try:
                    telegram_admin = TelegramAdmin.objects.filter(username=request.user.username).first()
                    if telegram_admin:
                        admin_id = telegram_admin.telegram_id
                except Exception:
                    pass
            
        except Exception as e:
            logger.warning(f"Не удалось получить telegram_id админа: {e}")
        
        return admin_id
    
    @admin.action(description='🚫 Забанить автора комментария на 1 час')
    def ban_author_1_hour(self, request, queryset):
        """Банит авторов комментариев на 1 час (использует существующую логику из MiniAppUser)."""
        admin_id = self.get_admin_telegram_id(request)
        count = 0
        for report in queryset:
            if report.comment:
                author_id = report.comment.author_telegram_id
                try:
                    from accounts.models import MiniAppUser
                    author_user = MiniAppUser.objects.filter(telegram_id=author_id).first()
                    if author_user:
                        author_user.ban_user(
                            duration_hours=1,
                            reason=f'Блокировка по жалобе #{report.id} ({report.get_reason_display()})',
                            admin_id=admin_id
                        )
                        report.is_reviewed = True
                        report.save()
                        count += 1
                except Exception as e:
                    logger.error(f"Ошибка блокировки пользователя {author_id}: {e}")
        self.message_user(request, f'Заблокировано {count} авторов комментариев на 1 час', messages.SUCCESS)
    
    @admin.action(description='🚫 Забанить автора комментария на 24 часа')
    def ban_author_24_hours(self, request, queryset):
        """Банит авторов комментариев на 24 часа (использует существующую логику из MiniAppUser)."""
        admin_id = self.get_admin_telegram_id(request)
        count = 0
        for report in queryset:
            if report.comment:
                author_id = report.comment.author_telegram_id
                try:
                    from accounts.models import MiniAppUser
                    author_user = MiniAppUser.objects.filter(telegram_id=author_id).first()
                    if author_user:
                        author_user.ban_user(
                            duration_hours=24,
                            reason=f'Блокировка по жалобе #{report.id} ({report.get_reason_display()})',
                            admin_id=admin_id
                        )
                        report.is_reviewed = True
                        report.save()
                        count += 1
                except Exception as e:
                    logger.error(f"Ошибка блокировки пользователя {author_id}: {e}")
        self.message_user(request, f'Заблокировано {count} авторов комментариев на 24 часа', messages.SUCCESS)
    
    @admin.action(description='🚫 Забанить автора комментария на 7 дней')
    def ban_author_7_days(self, request, queryset):
        """Банит авторов комментариев на 7 дней (использует существующую логику из MiniAppUser)."""
        admin_id = self.get_admin_telegram_id(request)
        count = 0
        for report in queryset:
            if report.comment:
                author_id = report.comment.author_telegram_id
                try:
                    from accounts.models import MiniAppUser
                    author_user = MiniAppUser.objects.filter(telegram_id=author_id).first()
                    if author_user:
                        author_user.ban_user(
                            duration_hours=168,  # 7 * 24
                            reason=f'Блокировка по жалобе #{report.id} ({report.get_reason_display()})',
                            admin_id=admin_id
                        )
                        report.is_reviewed = True
                        report.save()
                        count += 1
                except Exception as e:
                    logger.error(f"Ошибка блокировки пользователя {author_id}: {e}")
        self.message_user(request, f'Заблокировано {count} авторов комментариев на 7 дней', messages.SUCCESS)
    
    @admin.action(description='🚫 Перманентно забанить автора комментария')
    def ban_author_permanent(self, request, queryset):
        """Банит авторов комментариев навсегда (использует существующую логику из MiniAppUser)."""
        admin_id = self.get_admin_telegram_id(request)
        count = 0
        for report in queryset:
            if report.comment:
                author_id = report.comment.author_telegram_id
                try:
                    from accounts.models import MiniAppUser
                    author_user = MiniAppUser.objects.filter(telegram_id=author_id).first()
                    if author_user:
                        author_user.ban_user(
                            duration_hours=None,
                            reason=f'Перманентная блокировка по жалобе #{report.id} ({report.get_reason_display()})',
                            admin_id=admin_id
                        )
                        report.is_reviewed = True
                        report.save()
                        count += 1
                except Exception as e:
                    logger.error(f"Ошибка блокировки пользователя {author_id}: {e}")
        self.message_user(request, f'Заблокировано {count} авторов комментариев навсегда', messages.WARNING)
    
    @admin.action(description='✅ Разбанить автора комментария')
    def unban_author(self, request, queryset):
        """Разбанивает авторов комментариев (использует существующую логику из MiniAppUser)."""
        count = 0
        for report in queryset:
            if report.comment:
                author_id = report.comment.author_telegram_id
                try:
                    from accounts.models import MiniAppUser
                    author_user = MiniAppUser.objects.filter(telegram_id=author_id).first()
                    if author_user and author_user.is_banned:
                        author_user.unban_user()
                        count += 1
                except Exception as e:
                    logger.error(f"Ошибка разблокировки пользователя {author_id}: {e}")
        self.message_user(request, f'Разблокировано {count} авторов комментариев', messages.SUCCESS)
    
    def get_urls(self):
        """Добавляем кастомные URL для блокировки пользователя прямо из интерфейса жалобы."""
        from django.urls import path
        from django.shortcuts import redirect
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:report_id>/ban/<int:hours>/',
                self.admin_site.admin_view(self.ban_user_view),
                name='tasks_taskcommentreport_ban_user',
            ),
            path(
                '<int:report_id>/unban/',
                self.admin_site.admin_view(self.unban_user_view),
                name='tasks_taskcommentreport_unban_user',
            ),
        ]
        return custom_urls + urls
    
    def ban_user_view(self, request, report_id, hours):
        """Блокирует пользователя на указанное время (использует существующую логику из MiniAppUser)."""
        try:
            report = TaskCommentReport.objects.get(id=report_id)
            author_id = report.comment.author_telegram_id
            
            from accounts.models import MiniAppUser
            author_user = MiniAppUser.objects.filter(telegram_id=author_id).first()
            
            if not author_user:
                self.message_user(
                    request,
                    f'❌ Пользователь с ID {author_id} не найден в системе',
                    messages.ERROR
                )
                try:
                    return redirect('admin:tasks_taskcommentreport_change', report_id)
                except Exception:
                    return redirect(f'/admin/tasks/taskcommentreport/{report_id}/change/')
            
            admin_id = self.get_admin_telegram_id(request)
            
            if hours == 0:
                # Перманентный бан
                author_user.ban_user(
                    duration_hours=None,
                    reason=f'Блокировка по жалобе #{report_id} ({report.get_reason_display()})',
                    admin_id=admin_id
                )
                duration_text = 'навсегда'
            else:
                author_user.ban_user(
                    duration_hours=hours,
                    reason=f'Блокировка по жалобе #{report_id} ({report.get_reason_display()})',
                    admin_id=admin_id
                )
                if hours == 1:
                    duration_text = 'на 1 час'
                elif hours == 24:
                    duration_text = 'на 24 часа'
                elif hours == 168:
                    duration_text = 'на 7 дней'
                else:
                    duration_text = f'на {hours} часов'
            
            # Отмечаем жалобу как проверенную
            report.is_reviewed = True
            report.save()
            
            self.message_user(
                request,
                f'✅ Пользователь @{author_user.username or "без username"} (ID: {author_id}) заблокирован {duration_text}',
                messages.SUCCESS
            )
        except TaskCommentReport.DoesNotExist:
            self.message_user(request, '❌ Жалоба не найдена', messages.ERROR)
        except Exception as e:
            logger.error(f"Ошибка блокировки пользователя: {e}", exc_info=True)
            self.message_user(request, f'❌ Ошибка блокировки: {str(e)}', messages.ERROR)
        
        try:
            return redirect('admin:tasks_taskcommentreport_change', report_id)
        except Exception:
            return redirect(f'/admin/tasks/taskcommentreport/{report_id}/change/')
    
    def unban_user_view(self, request, report_id):
        """Разблокирует пользователя (использует существующую логику из MiniAppUser)."""
        try:
            report = TaskCommentReport.objects.get(id=report_id)
            author_id = report.comment.author_telegram_id
            
            from accounts.models import MiniAppUser
            author_user = MiniAppUser.objects.filter(telegram_id=author_id).first()
            
            if not author_user:
                self.message_user(
                    request,
                    f'❌ Пользователь с ID {author_id} не найден в системе',
                    messages.ERROR
                )
                try:
                    return redirect('admin:tasks_taskcommentreport_change', report_id)
                except Exception:
                    return redirect(f'/admin/tasks/taskcommentreport/{report_id}/change/')
            
            if not author_user.is_banned:
                self.message_user(
                    request,
                    f'ℹ️ Пользователь @{author_user.username or "без username"} (ID: {author_id}) не заблокирован',
                    messages.INFO
                )
                try:
                    return redirect('admin:tasks_taskcommentreport_change', report_id)
                except Exception:
                    return redirect(f'/admin/tasks/taskcommentreport/{report_id}/change/')
            
            author_user.unban_user()
            
            self.message_user(
                request,
                f'✅ Пользователь @{author_user.username or "без username"} (ID: {author_id}) разблокирован',
                messages.SUCCESS
            )
        except TaskCommentReport.DoesNotExist:
            self.message_user(request, '❌ Жалоба не найдена', messages.ERROR)
        except Exception as e:
            logger.error(f"Ошибка разблокировки пользователя: {e}", exc_info=True)
            self.message_user(request, f'❌ Ошибка разблокировки: {str(e)}', messages.ERROR)
        
        try:
            return redirect('admin:tasks_taskcommentreport_change', report_id)
        except Exception:
            return redirect(f'/admin/tasks/taskcommentreport/{report_id}/change/')

