import os
from django import forms
from django.contrib import admin
from django.conf import settings
from .models import Topic, Subtopic, TopicTranslation, SubtopicTranslation
from .utils import normalize_subtopic_name
from tenants.mixins import TenantFilteredAdminMixin


class TenantAccessibleTranslationInline(admin.TabularInline):
    """
    Даем доступ к inline-переводам всем staff-пользователям, у которых уже есть
    доступ к родительской модели. Иначе Django скрывает inline из-за отсутствия
    отдельных прав на новые translation-модели.
    """

    extra = 1

    def has_view_or_change_permission(self, request, obj=None):
        return bool(request.user and request.user.is_staff)

    def has_add_permission(self, request, obj=None):
        return bool(request.user and request.user.is_staff)

    def has_delete_permission(self, request, obj=None):
        return bool(request.user and request.user.is_staff)


class TopicTranslationInline(TenantAccessibleTranslationInline):
    model = TopicTranslation
    fields = ('language_code', 'name', 'description')


class SubtopicTranslationInline(TenantAccessibleTranslationInline):
    model = SubtopicTranslation
    fields = ('language_code', 'name', 'description')


class TopicAdminForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        icons_dir = os.path.join(settings.BASE_DIR, 'blog', 'static', 'blog', 'images', 'icons')
        choices = [('', '--- Выберите иконку ---')]

        if os.path.exists(icons_dir):
            icon_files = []
            for filename in os.listdir(icons_dir):
                if filename.endswith(('.png', '.jpg', '.jpeg', '.svg')):
                    icon_files.append(filename)

            icon_files.sort()

            for filename in icon_files:
                icon_path = f'/static/blog/images/icons/{filename}'
                display_name = filename.replace('-icon.png', '').replace('-icon.svg', '').replace('-', ' ').title()
                choices.append((icon_path, f"{display_name} ({filename})"))

        self.fields['icon'] = forms.ChoiceField(
            choices=choices,
            required=False,
            help_text='Выберите иконку для темы'
        )


@admin.register(Topic)
class TopicAdmin(TenantFilteredAdminMixin, admin.ModelAdmin):
    """
    Админка для управления темами.
    Контент-менеджеры видят только темы своего тенанта.
    Суперпользователь видит все темы всех тенантов.
    """
    form = TopicAdminForm
    inlines = [TopicTranslationInline]
    list_display = ('id', 'name', 'icon_preview', 'media_type', 'media_preview', 'description', 'get_subtopics_count')
    search_fields = ('name', 'description', 'translations__name', 'translations__description')
    list_filter = ('media_type',)
    ordering = ('name',)

    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'description', 'icon', 'icon_svg', 'icon_image'),
            'description': 'Базовые поля остаются как fallback для существующих данных и случаев, когда перевод еще не заполнен.'
        }),
        ('Медиа для карточки в карусели', {
            'fields': ('media_type', 'card_image', 'card_video', 'video_poster'),
            'description': 'Загрузите изображение, GIF или видео для отображения в карусели мини-приложения. Для видео можно загрузить постер (превью). Максимальный размер файла: 50 МБ.'
        }),
    )

    def get_subtopics_count(self, obj):
        """Получить количество подтем"""
        return obj.subtopics.count()
    get_subtopics_count.short_description = 'Количество подтем'

    def icon_preview(self, obj):
        if obj.icon_svg:
            return f'<div style="width: 32px; height: 32px; color: #ff9a00;">{obj.icon_svg}</div>'
        if obj.icon_image:
            return f'<img src="{obj.icon_image.url}" alt="{obj.name}" style="width: 32px; height: 32px; object-fit: contain;">'
        if obj.icon:
            return f'<img src="{obj.icon}" alt="{obj.name}" style="width: 32px; height: 32px; object-fit: contain;">'
        return 'Нет иконки'
    icon_preview.short_description = 'Иконка'
    icon_preview.allow_tags = True

    def media_preview(self, obj):
        """Превью медиа для карточки"""
        if obj.media_type == 'image' and obj.card_image:
            return f'<img src="{obj.card_image.url}" alt="{obj.name}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 4px;">'
        if obj.media_type == 'video' and obj.card_video:
            return f'<video src="{obj.card_video.url}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 4px;" muted></video>'
        if obj.media_type == 'default':
            return '📷 По умолчанию'
        return '❌ Нет медиа'
    media_preview.short_description = 'Превью медиа'
    media_preview.allow_tags = True


@admin.register(Subtopic)
class SubtopicAdmin(TenantFilteredAdminMixin, admin.ModelAdmin):
    """
    Админка для управления подтемами.
    Контент-менеджеры видят только подтемы своего тенанта.
    Суперпользователь видит все подтемы всех тенантов.
    """
    tenant_lookup = 'topic__tenant'
    inlines = [SubtopicTranslationInline]
    list_display = ('id', 'name', 'topic', 'get_tenant', 'get_tasks_count')
    search_fields = ('name', 'translations__name', 'topic__name', 'topic__translations__name')
    raw_id_fields = ('topic',)
    ordering = ('topic', 'name')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('topic', 'topic__tenant')

    def get_list_filter(self, request):
        """
        У tenant-admin не показываем фильтр по tenant и ограничиваем список тем
        только темами из его видимого queryset.
        """
        topic_filter = ('topic', admin.RelatedOnlyFieldListFilter)
        if request.user.is_superuser:
            return ('topic__tenant', topic_filter)
        return (topic_filter,)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'topic' and not request.user.is_superuser:
            tenant = getattr(request.user, 'tenant', None)
            if tenant:
                kwargs['queryset'] = Topic.objects.filter(tenant=tenant)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_tenant(self, obj):
        """Получить тенанта через тему"""
        return obj.topic.tenant if obj.topic else None
    get_tenant.short_description = 'Тенант'

    def save_model(self, request, obj, form, change):
        """
        Нормализует имя подтемы перед сохранением через админку.
        """
        if obj.name:
            obj.name = normalize_subtopic_name(obj.name)
        super().save_model(request, obj, form, change)

    def get_tasks_count(self, obj):
        """Получить количество задач в подтеме"""
        return obj.tasks.count()
    get_tasks_count.short_description = 'Количество задач'
