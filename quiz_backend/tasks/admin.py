import os
from django import forms
from django.contrib import admin, messages
from django.urls import path
from django.shortcuts import render, redirect
from django.conf import settings
from django.utils.html import format_html
from django.utils import timezone
from .models import Task, TaskTranslation, TaskStatistics, TaskPoll, MiniAppTaskStatistics, TaskComment, TaskCommentImage, TaskCommentReport
from .services.task_import_service import import_tasks_from_json
from accounts.models import MiniAppUser
from .services.s3_service import delete_image_from_s3
from .services.telegram_service import publish_task_to_telegram
from .services.image_generation_service import generate_image_for_task
from .services.s3_service import upload_image_to_s3
import uuid
import logging

logger = logging.getLogger(__name__)


class TaskTranslationInline(admin.TabularInline):
    """
    Inline редактирование переводов задачи.
    """
    model = TaskTranslation
    extra = 0
    fields = ('language', 'question', 'answers', 'correct_answer', 'explanation')
    readonly_fields = ('publish_date',)


class TaskAdminForm(forms.ModelForm):
    """
    Кастомная форма для Task с выпадающим списком ссылок.
    Подтягивает все DefaultLink из общей БД с ботом.
    """
    class Meta:
        model = Task
        fields = '__all__'
    
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
        
        # Делаем некоторые поля необязательными при редактировании существующей задачи
        if self.instance.pk:
            # При редактировании message_id не обязателен (он заполняется автоматически)
            if 'message_id' in self.fields:
                self.fields['message_id'].required = False
            
            # group может быть пустым (заполняется при импорте или можно выбрать позже)
            if 'group' in self.fields:
                self.fields['group'].required = False


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    """
    Админка для управления задачами с расширенной функциональностью:
    - Импорт из JSON
    - Публикация в Telegram
    - Генерация изображений
    - Умное удаление с очисткой S3
    """
    form = TaskAdminForm
    change_list_template = 'admin/tasks/task_changelist.html'
    
    list_display = ('id', 'topic', 'subtopic', 'difficulty', 'published', 'error_status', 'create_date', 'publish_date', 'has_image', 'has_external_link')
    list_filter = ('published', 'difficulty', 'topic', 'subtopic', 'error')
    search_fields = ('id', 'topic__name', 'subtopic__name', 'translation_group_id', 'external_link')
    raw_id_fields = ('topic', 'subtopic', 'group')
    date_hierarchy = 'create_date'
    ordering = ('-create_date',)
    list_per_page = 20
    
    # Добавляем поля для редактирования
    fieldsets = (
        ('Основная информация', {
            'fields': ('topic', 'subtopic', 'group', 'difficulty')
        }),
        ('Контент', {
            'fields': ('image_url', 'external_link', 'get_final_link_display'),
            'description': 'Ссылка используется для кнопки "Узнать больше о задаче" при публикации в Telegram'
        }),
        ('Публикация', {
            'fields': ('published', 'error')
        }),
        ('Системная информация', {
            'fields': ('translation_group_id', 'message_id', 'create_date', 'publish_date'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('create_date', 'publish_date', 'translation_group_id', 'message_id', 'get_final_link_display')
    
    # Inline редактирование переводов
    inlines = [TaskTranslationInline]
    
    actions = [
        'publish_to_telegram',
        'generate_images',
        'clear_error_flag',
        'delete_with_s3_cleanup'
    ]
    
    def has_image(self, obj):
        """Проверка наличия изображения."""
        return bool(obj.image_url)
    has_image.boolean = True
    has_image.short_description = 'Изображение'
    
    def has_external_link(self, obj):
        """Проверка наличия внешней ссылки."""
        return bool(obj.external_link)
    has_external_link.boolean = True
    has_external_link.short_description = 'Ссылка "Подробнее"'
    
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
    
    def get_urls(self):
        """Добавляем URL для импорта JSON."""
        urls = super().get_urls()
        custom_urls = [
            path('import-json/', self.admin_site.admin_view(self.import_json_view), name='tasks_task_import_json'),
        ]
        return custom_urls + urls
    
    def import_json_view(self, request):
        """
        Представление для импорта задач из JSON файла.
        """
        if request.method == 'POST':
            json_file = request.FILES.get('json_file')
            publish = request.POST.get('publish') == 'on'
            
            if not json_file:
                messages.error(request, 'Пожалуйста, выберите JSON файл.')
                return render(request, 'admin/tasks/import_json.html')
            
            # Сохраняем файл временно
            temp_path = os.path.join(settings.MEDIA_ROOT, 'temp', json_file.name)
            os.makedirs(os.path.dirname(temp_path), exist_ok=True)
            
            with open(temp_path, 'wb+') as destination:
                for chunk in json_file.chunks():
                    destination.write(chunk)
            
            try:
                # Импортируем задачи
                result = import_tasks_from_json(temp_path, publish=publish)
                
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
    
    def get_deleted_objects(self, objs, request):
        """
        Переопределяем метод для отображения всех связанных задач, 
        которые будут удалены вместе с выбранными.
        """
        from django.contrib.admin.utils import NestedObjects
        from django.db import router
        
        collector = NestedObjects(using=router.db_for_write(Task))
        
        # Для каждого объекта находим все связанные задачи по translation_group_id
        all_tasks_to_delete = set()
        for obj in objs:
            if obj.translation_group_id:
                related_tasks = Task.objects.filter(
                    translation_group_id=obj.translation_group_id
                )
                all_tasks_to_delete.update(related_tasks)
            else:
                all_tasks_to_delete.add(obj)
        
        # Собираем все объекты для удаления
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
        
        to_delete = collector.nested(format_callback)
        
        # Считаем количество объектов каждого типа
        model_count = {
            model._meta.verbose_name_plural: len(objs_list)
            for model, objs_list in collector.model_objs.items()
        }
        
        return to_delete, model_count, perms_needed, protected
    
    def delete_model(self, request, obj):
        """
        Переопределяем удаление одной задачи для очистки связанных ресурсов.
        Удаляет все связанные задачи по translation_group_id и их изображения из S3.
        """
        from django.db.models.signals import pre_delete
        from .signals import delete_related_tasks_and_images
        
        translation_group_id = obj.translation_group_id
        
        if translation_group_id:
            # Находим все связанные задачи
            related_tasks = Task.objects.filter(translation_group_id=translation_group_id)
            
            # Собираем информацию о языках ДО удаления
            languages = []
            for task in related_tasks:
                translation = task.translations.first()
                if translation:
                    languages.append(translation.language.upper())
            
            # Собираем URL изображений ОДИН РАЗ
            image_urls = list(set([task.image_url for task in related_tasks if task.image_url]))
            
            count = related_tasks.count()
            
            # Удаляем изображения из S3
            for image_url in image_urls:
                delete_image_from_s3(image_url)
            
            # ОТКЛЮЧАЕМ СИГНАЛ чтобы избежать дублирования
            pre_delete.disconnect(delete_related_tasks_and_images, sender=Task)
            
            try:
                # Удаляем все связанные задачи
                related_tasks.delete()
            finally:
                # ВКЛЮЧАЕМ СИГНАЛ обратно
                pre_delete.connect(delete_related_tasks_and_images, sender=Task)
            
            lang_info = ", ".join(languages) if languages else ""
            
            messages.success(
                request,
                f"Удалено {count} связанных задач ({lang_info}) и {len(image_urls)} изображений из S3"
            )
        else:
            # Обычное удаление
            super().delete_model(request, obj)
    
    def delete_queryset(self, request, queryset):
        """
        Переопределяем массовое удаление для очистки связанных ресурсов.
        """
        from django.db.models.signals import pre_delete
        from .signals import delete_related_tasks_and_images
        
        # Собираем все translation_group_id
        translation_group_ids = set(
            queryset.values_list('translation_group_id', flat=True)
        )
        
        # Находим все связанные задачи
        all_related_tasks = Task.objects.filter(
            translation_group_id__in=translation_group_ids
        )
        
        # Собираем информацию о языках ДО удаления
        languages = []
        for task in all_related_tasks:
            translation = task.translations.first()
            if translation:
                languages.append(translation.language.upper())
        
        # Собираем URL изображений ОДИН РАЗ (используем set для уникальности)
        image_urls = list(set([task.image_url for task in all_related_tasks if task.image_url]))
        
        count = all_related_tasks.count()
        
        # Удаляем изображения из S3
        deleted_images = 0
        for image_url in image_urls:
            if delete_image_from_s3(image_url):
                deleted_images += 1
        
        # ОТКЛЮЧАЕМ СИГНАЛ чтобы избежать дублирования
        pre_delete.disconnect(delete_related_tasks_and_images, sender=Task)
        
        try:
            # Удаляем все связанные задачи
            all_related_tasks.delete()
        finally:
            # ВКЛЮЧАЕМ СИГНАЛ обратно
            pre_delete.connect(delete_related_tasks_and_images, sender=Task)
        
        lang_info = ", ".join(sorted(set(languages))) if languages else ""
        
        messages.success(
            request,
            f"Удалено {count} задач ({lang_info}) и {deleted_images} изображений из S3"
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
        ).select_related('topic', 'group').prefetch_related('translations')
        
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
        
        for task in all_related_tasks:
            translation = task.translations.first()
            if not translation:
                error_msg = f"Задача {task.id}: отсутствуют переводы"
                errors.append(error_msg)
                self.message_user(request, f"⚠️ {error_msg}", messages.WARNING)
                continue
            
            language = translation.language.upper()
            
            # Проверяем наличие изображения
            if not task.image_url:
                error_msg = f"Задача {task.id} ({language}): отсутствует изображение"
                errors.append(error_msg)
                self.message_user(request, f"⚠️ {error_msg}", messages.WARNING)
                continue
            
            # Находим группу для этого языка и топика
            telegram_group = TelegramGroup.objects.filter(
                topic_id=task.topic,
                language=translation.language
            ).first()
            
            if not telegram_group:
                error_msg = f"Задача {task.id} ({language}): не найдена Telegram группа для языка {language}"
                errors.append(error_msg)
                self.message_user(request, f"⚠️ {error_msg}", messages.WARNING)
                continue
            
            try:
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
                
                # Показываем детальные логи публикации
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
                    # Обновляем флаг публикации и дату для этой задачи
                    task.published = True
                    task.publish_date = timezone.now()
                    task.error = False  # Сбрасываем ошибку если публикация успешна
                    task.save(update_fields=['published', 'publish_date', 'error'])
                    published_count += 1
                    
                    # Считаем по языкам
                    if language not in published_by_language:
                        published_by_language[language] = 0
                    published_by_language[language] += 1
                else:
                    # Отмечаем ошибку для ЭТОЙ задачи, остальные переводы продолжают публиковаться
                    task.error = True
                    task.save(update_fields=['error'])
                    error_details = ', '.join(result['errors'])
                    errors.append(f"Задача {task.id} ({language}): {error_details}")
                    
            except Exception as e:
                # Отмечаем ошибку при исключении
                task.error = True
                task.save(update_fields=['error'])
                error_msg = f"Задача {task.id} ({language}): {str(e)}"
                errors.append(error_msg)
                self.message_user(request, f"❌ {error_msg}", messages.ERROR)
        
        # Итоговое сообщение
        self.message_user(request, "=" * 60, messages.INFO)
        
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
                    # Загружаем в S3
                    image_name = f"tasks/{task.id}_{uuid.uuid4().hex[:8]}.png"
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
    
    @admin.action(description='Удалить с очисткой S3')
    def delete_with_s3_cleanup(self, request, queryset):
        """
        Удаляет задачи с очисткой изображений из S3.
        """
        self.delete_queryset(request, queryset)


@admin.register(TaskTranslation)
class TaskTranslationAdmin(admin.ModelAdmin):
    """
    Админка для переводов задач.
    """
    list_display = ('id', 'task', 'language', 'question_preview')  # Добавим укороченный вопрос
    list_filter = ('language',)
    search_fields = ('question', 'correct_answer', 'task__id')
    raw_id_fields = ('task',)
    list_per_page = 20

    def question_preview(self, obj):
        """Отображает первые 50 символов вопроса."""
        return obj.question[:50] + ('...' if len(obj.question) > 50 else '')
    question_preview.short_description = 'Вопрос (превью)'


@admin.register(TaskStatistics)
class TaskStatisticsAdmin(admin.ModelAdmin):
    """
    Админка для статистики решения задач.
    """
    list_display = ('user', 'task', 'attempts', 'successful', 'last_attempt_date')
    list_filter = ('successful',)
    search_fields = ('user__username', 'task__id')
    raw_id_fields = ('user', 'task')
    date_hierarchy = 'last_attempt_date'
    list_per_page = 20


@admin.register(TaskPoll)
class TaskPollAdmin(admin.ModelAdmin):
    """
    Админка для опросов задач.
    """
    list_display = ('task', 'poll_id', 'is_anonymous', 'total_voter_count', 'poll_question_preview')
    list_filter = ('is_anonymous', 'allows_multiple_answers')
    search_fields = ('poll_id', 'task__id', 'poll_question')
    raw_id_fields = ('task', 'translation')
    list_per_page = 20

    def poll_question_preview(self, obj):
        """Отображает первые 50 символов вопроса опроса."""
        return obj.poll_question[:50] + ('...' if len(obj.poll_question) > 50 else '')
    poll_question_preview.short_description = 'Вопрос опроса (превью)'


@admin.register(MiniAppTaskStatistics)
class MiniAppTaskStatisticsAdmin(admin.ModelAdmin):
    """
    Админка для статистики решения задач пользователями Mini App.
    """
    list_display = ('mini_app_user', 'task', 'attempts', 'successful', 'last_attempt_date', 'is_linked')
    list_filter = ('successful', 'last_attempt_date', 'mini_app_user__language')
    search_fields = ('mini_app_user__telegram_id', 'mini_app_user__username', 'task__id')
    raw_id_fields = ('mini_app_user', 'task', 'linked_statistics')
    date_hierarchy = 'last_attempt_date'
    list_per_page = 20
    readonly_fields = ('last_attempt_date', 'is_linked')

    def is_linked(self, obj):
        """Показывает, связана ли статистика с основной статистикой"""
        return bool(obj.linked_statistics)
    is_linked.boolean = True
    is_linked.short_description = 'Связана с основной статистикой'

    actions = ['merge_to_main_statistics']

    def merge_to_main_statistics(self, request, queryset):
        """
        Объединяет выбранную статистику мини-аппа с основной статистикой.
        """
        merged_count = 0
        errors = []

        for mini_app_stats in queryset:
            try:
                # Проверяем, есть ли связанный CustomUser
                mini_app_user = mini_app_stats.mini_app_user

                # Ищем CustomUser по telegram_id
                from accounts.models import CustomUser
                try:
                    custom_user = CustomUser.objects.get(telegram_id=mini_app_user.telegram_id)
                    mini_app_stats.merge_to_main_statistics(custom_user)
                    merged_count += 1
                except CustomUser.DoesNotExist:
                    errors.append(f"Пользователь с telegram_id {mini_app_user.telegram_id} не найден в CustomUser")

            except Exception as e:
                errors.append(f"Ошибка при объединении статистики {mini_app_stats.id}: {e}")

        if merged_count > 0:
            self.message_user(request, f"Успешно объединено {merged_count} записей статистики.")

        if errors:
            for error in errors:
                self.message_user(request, error, level='ERROR')

    merge_to_main_statistics.short_description = "Объединить с основной статистикой"


class TaskCommentImageInline(admin.TabularInline):
    """Inline для изображений комментариев."""
    model = TaskCommentImage
    extra = 0
    fields = ('image_preview', 'image', 'file_size_display', 'uploaded_at')
    readonly_fields = ('uploaded_at', 'image_preview', 'file_size_display')
    
    def image_preview(self, obj):
        """Превью изображения."""
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width: 150px; max-height: 150px; border-radius: 4px; border: 2px solid #007bff;" />',
                obj.image.url
            )
        return '—'
    image_preview.short_description = 'Превью'
    
    def file_size_display(self, obj):
        """Размер файла."""
        if obj.image:
            size_bytes = obj.image.size
            if size_bytes < 1024:
                return f'{size_bytes} B'
            elif size_bytes < 1024 * 1024:
                return f'{size_bytes / 1024:.1f} KB'
            else:
                return f'{size_bytes / (1024 * 1024):.2f} MB'
        return '—'
    file_size_display.short_description = 'Размер'


@admin.register(TaskCommentImage)
class TaskCommentImageAdmin(admin.ModelAdmin):
    """Админка для управления изображениями комментариев."""
    list_display = ('id', 'image_preview_list', 'comment_link', 'file_size_display', 'uploaded_at')
    list_filter = ('uploaded_at',)
    search_fields = ('comment__text', 'comment__author_username')
    raw_id_fields = ('comment',)
    date_hierarchy = 'uploaded_at'
    list_per_page = 30
    readonly_fields = ('uploaded_at', 'image_preview_large', 'file_info')
    
    fieldsets = (
        ('Изображение', {
            'fields': ('image', 'image_preview_large', 'file_info')
        }),
        ('Связанный комментарий', {
            'fields': ('comment', 'uploaded_at')
        }),
    )
    
    def image_preview_list(self, obj):
        """Превью изображения в списке."""
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width: 80px; max-height: 80px; border-radius: 4px; border: 2px solid #007bff; cursor: pointer;" onclick="window.open(\'{}\', \'_blank\')" title="Кликните для открытия в полном размере" />',
                obj.image.url,
                obj.image.url
            )
        return '—'
    image_preview_list.short_description = 'Превью'
    
    def image_preview_large(self, obj):
        """Большое превью изображения."""
        if obj.image:
            return format_html(
                '<div style="text-align: center; padding: 20px; background: #f8f9fa; border-radius: 8px;"><img src="{}" style="max-width: 600px; max-height: 600px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);" /><br><a href="{}" target="_blank" style="margin-top: 10px; display: inline-block; padding: 8px 16px; background: #007bff; color: white; text-decoration: none; border-radius: 4px;">🔗 Открыть в полном размере</a></div>',
                obj.image.url,
                obj.image.url
            )
        return '—'
    image_preview_large.short_description = 'Изображение'
    
    def comment_link(self, obj):
        """Ссылка на комментарий."""
        text_preview = obj.comment.text[:30] + '...' if len(obj.comment.text) > 30 else obj.comment.text
        return format_html(
            '<a href="/admin/tasks/taskcomment/{}/change/" target="_blank">💬 {}</a>',
            obj.comment.id,
            text_preview
        )
    comment_link.short_description = 'Комментарий'
    
    def file_size_display(self, obj):
        """Размер файла с цветовой индикацией."""
        if obj.image:
            size_bytes = obj.image.size
            
            if size_bytes < 1024 * 1024:  # < 1 MB
                size_str = f'{size_bytes / 1024:.1f} KB'
                color = '#28a745'  # зеленый
            elif size_bytes < 5 * 1024 * 1024:  # < 5 MB
                size_str = f'{size_bytes / (1024 * 1024):.2f} MB'
                color = '#ffc107'  # желтый
            else:  # >= 5 MB
                size_str = f'{size_bytes / (1024 * 1024):.2f} MB'
                color = '#dc3545'  # красный
            
            return format_html(
                '<span style="color: {}; font-weight: bold;">📦 {}</span>',
                color,
                size_str
            )
        return '—'
    file_size_display.short_description = 'Размер'
    
    def file_info(self, obj):
        """Полная информация о файле."""
        if obj.image:
            size_bytes = obj.image.size
            size_mb = size_bytes / (1024 * 1024)
            
            return format_html(
                '<div style="padding: 15px; background: #f8f9fa; border-radius: 8px; border-left: 4px solid #007bff;">'
                '<strong>📊 Информация о файле:</strong><br>'
                '<table style="margin-top: 10px; border-collapse: collapse;">'
                '<tr><td style="padding: 5px; font-weight: bold;">Размер:</td><td style="padding: 5px;">{:.2f} MB ({} bytes)</td></tr>'
                '<tr><td style="padding: 5px; font-weight: bold;">Имя файла:</td><td style="padding: 5px;">{}</td></tr>'
                '<tr><td style="padding: 5px; font-weight: bold;">URL:</td><td style="padding: 5px;"><a href="{}" target="_blank">{}</a></td></tr>'
                '</table>'
                '</div>',
                size_mb,
                size_bytes,
                obj.image.name.split('/')[-1],
                obj.image.url,
                obj.image.url
            )
        return '—'
    file_info.short_description = 'Информация о файле'


@admin.register(TaskComment)
class TaskCommentAdmin(admin.ModelAdmin):
    """Админка для модерации комментариев к задачам."""
    list_display = ('id', 'author_display', 'task_display', 'text_preview', 'images_count_display', 'replies_count_display', 'created_at', 'is_deleted', 'reports_count_display')
    list_filter = ('is_deleted', 'created_at', 'reports_count', 'task_translation__language')
    search_fields = ('author_username', 'author_telegram_id', 'text', 'task_translation__question')
    raw_id_fields = ('task_translation', 'parent_comment')
    date_hierarchy = 'created_at'
    list_per_page = 20
    readonly_fields = ('created_at', 'updated_at', 'reports_count', 'get_depth', 'get_replies_count', 'author_profile_link', 'images_preview')
    
    fieldsets = (
        ('Автор', {
            'fields': ('author_telegram_id', 'author_username', 'author_profile_link')
        }),
        ('Содержание', {
            'fields': ('task_translation', 'text', 'parent_comment', 'images_preview')
        }),
        ('Статус', {
            'fields': ('is_deleted', 'reports_count', 'get_depth', 'get_replies_count')
        }),
        ('Даты', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [TaskCommentImageInline]
    
    actions = ['mark_as_deleted', 'restore_comments']
    
    def text_preview(self, obj):
        """Превью текста комментария."""
        return obj.text[:50] + ('...' if len(obj.text) > 50 else '')
    text_preview.short_description = 'Текст (превью)'
    
    def reports_count_display(self, obj):
        """Отображение количества жалоб с цветовой индикацией."""
        if obj.reports_count == 0:
            return format_html('<span style="color: #28a745;">0</span>')
        elif obj.reports_count < 3:
            return format_html('<span style="color: #ffc107; font-weight: bold;">{}</span>', obj.reports_count)
        else:
            return format_html('<span style="color: #dc3545; font-weight: bold;">⚠️ {}</span>', obj.reports_count)
    reports_count_display.short_description = 'Жалобы'
    
    def get_depth(self, obj):
        """Отображение глубины вложенности."""
        depth = obj.get_depth()
        return f"Уровень {depth}"
    get_depth.short_description = 'Глубина'
    
    def get_replies_count(self, obj):
        """Отображение количества ответов."""
        return obj.get_replies_count()
    get_replies_count.short_description = 'Ответов'
    
    def author_display(self, obj):
        """Красивое отображение автора с username из MiniAppUser."""
        try:
            user = MiniAppUser.objects.get(telegram_id=obj.author_telegram_id)
            return format_html(
                '<strong>{}</strong><br><small style="color: #666;">@{} (ID: {})</small>',
                user.first_name or user.username or 'Без имени',
                user.username or 'нет',
                obj.author_telegram_id
            )
        except MiniAppUser.DoesNotExist:
            return format_html(
                '<span style="color: #dc3545;">{}</span><br><small>(ID: {})</small>',
                obj.author_username,
                obj.author_telegram_id
            )
    author_display.short_description = 'Автор'
    
    def task_display(self, obj):
        """Красивое отображение задачи с языком."""
        lang_emoji = '🇷🇺' if obj.task_translation.language == 'ru' else '🇬🇧'
        question_preview = obj.task_translation.question[:40] + '...' if len(obj.task_translation.question) > 40 else obj.task_translation.question
        return format_html(
            '{} <strong>Задача #{}</strong><br><small>{}</small>',
            lang_emoji,
            obj.task_translation.task_id,
            question_preview
        )
    task_display.short_description = 'Задача'
    
    def images_count_display(self, obj):
        """Количество изображений в комментарии."""
        count = obj.images.count()
        if count > 0:
            return format_html('<span style="color: #007bff;">📷 {}</span>', count)
        return '—'
    images_count_display.short_description = 'Фото'
    
    def replies_count_display(self, obj):
        """Количество ответов на комментарий."""
        count = obj.get_replies_count()
        if count > 0:
            return format_html('<span style="color: #17a2b8;">💬 {}</span>', count)
        return '—'
    replies_count_display.short_description = 'Ответы'
    
    def author_profile_link(self, obj):
        """Ссылка на профиль пользователя."""
        try:
            user = MiniAppUser.objects.get(telegram_id=obj.author_telegram_id)
            return format_html(
                '<a href="/admin/accounts/miniappuser/{}/change/" target="_blank" style="padding: 8px 16px; background: #007bff; color: white; text-decoration: none; border-radius: 4px; display: inline-block;">👤 Открыть профиль: {} (@{})</a>',
                user.id,
                user.first_name or user.username,
                user.username or 'нет'
            )
        except MiniAppUser.DoesNotExist:
            return format_html('<span style="color: #dc3545;">❌ Пользователь не найден (Telegram ID: {})</span>', obj.author_telegram_id)
    author_profile_link.short_description = 'Профиль автора'
    
    def images_preview(self, obj):
        """Превью изображений комментария."""
        images = obj.images.all()
        if not images:
            return 'Нет изображений'
        
        html = '<div style="display: flex; gap: 10px; flex-wrap: wrap; margin-top: 10px;">'
        for img in images:
            html += f'''
                <div style="border: 2px solid #007bff; padding: 8px; border-radius: 8px; background: #f8f9fa;">
                    <img src="{img.image.url}" style="max-width: 200px; max-height: 200px; display: block; border-radius: 4px;" />
                    <small style="color: #666; font-size: 11px; display: block; margin-top: 5px;">📅 {img.uploaded_at.strftime("%d.%m.%Y %H:%M")}</small>
                </div>
            '''
        html += '</div>'
        return format_html(html)
    images_preview.short_description = 'Превью изображений'
    
    @admin.action(description='Пометить как удалённые')
    def mark_as_deleted(self, request, queryset):
        """Мягкое удаление выбранных комментариев."""
        updated = queryset.update(is_deleted=True, text='[Комментарий удалён модератором]')
        self.message_user(request, f'Удалено {updated} комментариев', messages.SUCCESS)
    
    @admin.action(description='Восстановить комментарии')
    def restore_comments(self, request, queryset):
        """Восстановление удалённых комментариев."""
        updated = queryset.update(is_deleted=False)
        self.message_user(request, f'Восстановлено {updated} комментариев', messages.SUCCESS)


@admin.register(TaskCommentReport)
class TaskCommentReportAdmin(admin.ModelAdmin):
    """Админка для жалоб на комментарии."""
    list_display = ('id', 'reporter_display', 'comment_preview', 'reason_display', 'created_at', 'is_reviewed_display')
    list_filter = ('is_reviewed', 'reason', 'created_at')
    search_fields = ('comment__text', 'reporter_telegram_id', 'description', 'comment__author_username')
    raw_id_fields = ('comment',)
    date_hierarchy = 'created_at'
    list_per_page = 20
    readonly_fields = ('created_at', 'reporter_profile_link', 'comment_author_link', 'comment_full_text')
    
    fieldsets = (
        ('Кто пожаловался', {
            'fields': ('reporter_telegram_id', 'reporter_profile_link')
        }),
        ('На что жалоба', {
            'fields': ('comment', 'comment_author_link', 'comment_full_text')
        }),
        ('Причина жалобы', {
            'fields': ('reason', 'description')
        }),
        ('Модерация', {
            'fields': ('is_reviewed', 'created_at')
        }),
    )
    
    actions = ['mark_as_reviewed', 'delete_reported_comments']
    
    def comment_preview(self, obj):
        """Превью комментария."""
        text = obj.comment.text[:60] + ('...' if len(obj.comment.text) > 60 else '')
        img_count = obj.comment.images.count()
        img_badge = f' 📷{img_count}' if img_count > 0 else ''
        
        return format_html(
            '<a href="/admin/tasks/taskcomment/{}/change/" style="text-decoration: none;"><div style="padding: 8px; background: #f8f9fa; border-left: 3px solid #007bff; border-radius: 4px;"><strong>💬 Комментарий #{}</strong>{}<br><small style="color: #666;">{}</small></div></a>',
            obj.comment.id,
            obj.comment.id,
            img_badge,
            text
        )
    comment_preview.short_description = 'Комментарий'
    
    def reporter_display(self, obj):
        """Красивое отображение репортера с username."""
        try:
            user = MiniAppUser.objects.get(telegram_id=obj.reporter_telegram_id)
            return format_html(
                '<strong>🚨 {}</strong><br><small style="color: #666;">@{} (ID: {})</small>',
                user.first_name or user.username or 'Без имени',
                user.username or 'нет',
                obj.reporter_telegram_id
            )
        except MiniAppUser.DoesNotExist:
            return format_html(
                '<span style="color: #dc3545;">❌ Пользователь не найден</span><br><small>(ID: {})</small>',
                obj.reporter_telegram_id
            )
    reporter_display.short_description = 'Кто пожаловался'
    
    def reason_display(self, obj):
        """Красивое отображение причины жалобы."""
        reason_colors = {
            'spam': '#ffc107',
            'offensive': '#dc3545',
            'inappropriate': '#fd7e14',
            'other': '#6c757d'
        }
        reason_icons = {
            'spam': '📧',
            'offensive': '⚠️',
            'inappropriate': '🚫',
            'other': '❓'
        }
        color = reason_colors.get(obj.reason, '#6c757d')
        icon = reason_icons.get(obj.reason, '❓')
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color,
            icon,
            obj.get_reason_display()
        )
    reason_display.short_description = 'Причина'
    
    def is_reviewed_display(self, obj):
        """Красивое отображение статуса проверки."""
        if obj.is_reviewed:
            return format_html('<span style="color: #28a745; font-weight: bold;">✅ Проверено</span>')
        else:
            return format_html('<span style="color: #dc3545; font-weight: bold;">🔴 Новая</span>')
    is_reviewed_display.short_description = 'Статус'
    
    def reporter_profile_link(self, obj):
        """Ссылка на профиль репортера."""
        try:
            user = MiniAppUser.objects.get(telegram_id=obj.reporter_telegram_id)
            return format_html(
                '<a href="/admin/accounts/miniappuser/{}/change/" target="_blank" style="padding: 8px 16px; background: #dc3545; color: white; text-decoration: none; border-radius: 4px; display: inline-block;">🚨 Профиль пожаловавшегося: {} (@{})</a>',
                user.id,
                user.first_name or user.username,
                user.username or 'нет'
            )
        except MiniAppUser.DoesNotExist:
            return format_html('<span style="color: #dc3545;">❌ Пользователь не найден (Telegram ID: {})</span>', obj.reporter_telegram_id)
    reporter_profile_link.short_description = 'Профиль репортера'
    
    def comment_author_link(self, obj):
        """Ссылка на профиль автора комментария."""
        try:
            user = MiniAppUser.objects.get(telegram_id=obj.comment.author_telegram_id)
            return format_html(
                '<a href="/admin/accounts/miniappuser/{}/change/" target="_blank" style="padding: 8px 16px; background: #007bff; color: white; text-decoration: none; border-radius: 4px; display: inline-block;">👤 Профиль автора комментария: {} (@{})</a>',
                user.id,
                user.first_name or user.username,
                user.username or 'нет'
            )
        except MiniAppUser.DoesNotExist:
            return format_html('<span style="color: #dc3545;">❌ Пользователь не найден (Telegram ID: {})</span>', obj.comment.author_telegram_id)
    comment_author_link.short_description = 'Автор комментария'
    
    def comment_full_text(self, obj):
        """Полный текст комментария."""
        images = obj.comment.images.all()
        img_html = ''
        if images:
            img_html = '<div style="margin-top: 10px;"><strong>Изображения в комментарии:</strong><div style="display: flex; gap: 10px; margin-top: 5px;">'
            for img in images:
                img_html += f'<img src="{img.image.url}" style="max-width: 150px; max-height: 150px; border-radius: 4px; border: 1px solid #ddd;" />'
            img_html += '</div></div>'
        
        return format_html(
            '<div style="padding: 15px; background: #f8f9fa; border-radius: 8px; border-left: 4px solid #007bff;"><pre style="white-space: pre-wrap; font-family: inherit; margin: 0;">{}</pre>{}</div>',
            obj.comment.text,
            img_html
        )
    comment_full_text.short_description = 'Полный текст комментария'
    
    @admin.action(description='Отметить как проверенные')
    def mark_as_reviewed(self, request, queryset):
        """Отметить жалобы как проверенные."""
        updated = queryset.update(is_reviewed=True)
        self.message_user(request, f'Отмечено {updated} жалоб как проверенные', messages.SUCCESS)
    
    @admin.action(description='Удалить комментарии с жалобами')
    def delete_reported_comments(self, request, queryset):
        """Удаление комментариев, на которые поступили жалобы."""
        comments = TaskComment.objects.filter(id__in=queryset.values_list('comment_id', flat=True))
        count = comments.count()
        comments.update(is_deleted=True, text='[Комментарий удалён модератором]')
        queryset.update(is_reviewed=True)
        self.message_user(request, f'Удалено {count} комментариев', messages.SUCCESS)


