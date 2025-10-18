import os
from django.contrib import admin, messages
from django.urls import path
from django.shortcuts import render, redirect
from django.conf import settings
from .models import Task, TaskTranslation, TaskStatistics, TaskPoll, MiniAppTaskStatistics
from .services.task_import_service import import_tasks_from_json
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


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    """
    Админка для управления задачами с расширенной функциональностью:
    - Импорт из JSON
    - Публикация в Telegram
    - Генерация изображений
    - Умное удаление с очисткой S3
    """
    change_list_template = 'admin/tasks/task_changelist.html'
    
    list_display = ('id', 'topic', 'subtopic', 'difficulty', 'published', 'create_date', 'publish_date', 'has_image', 'has_external_link')
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
            'fields': ('image_url', 'external_link'),
            'description': 'External link используется для кнопки "Подробнее" при публикации в Telegram'
        }),
        ('Публикация', {
            'fields': ('published', 'error')
        }),
        ('Системная информация', {
            'fields': ('translation_group_id', 'message_id', 'create_date', 'publish_date'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('create_date', 'publish_date', 'translation_group_id', 'message_id')
    
    # Inline редактирование переводов
    inlines = [TaskTranslationInline]
    
    actions = [
        'publish_to_telegram',
        'generate_images',
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
                    telegram_group=telegram_group,
                    external_link=task.external_link
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
                    task.published = True
                    task.save(update_fields=['published'])
                    published_count += 1
                    
                    # Считаем по языкам
                    if language not in published_by_language:
                        published_by_language[language] = 0
                    published_by_language[language] += 1
                else:
                    error_details = ', '.join(result['errors'])
                    errors.append(f"Задача {task.id} ({language}): {error_details}")
                    
            except Exception as e:
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
                        task.save(update_fields=['image_url'])
                        generated_count += 1
                        self.message_user(request, f"✅ Задача {task.id}: изображение загружено в S3", messages.SUCCESS)
                        self.message_user(request, f"   URL: {image_url}", messages.INFO)
                    else:
                        error_msg = f"Задача {task.id}: не удалось загрузить в S3"
                        errors.append(error_msg)
                        self.message_user(request, f"❌ {error_msg}", messages.ERROR)
                else:
                    error_msg = f"Задача {task.id}: не удалось сгенерировать изображение"
                    errors.append(error_msg)
                    self.message_user(request, f"❌ {error_msg}", messages.ERROR)
            except Exception as e:
                error_msg = f"Задача {task.id}: {str(e)}"
                errors.append(error_msg)
                self.message_user(request, f"❌ {error_msg}", messages.ERROR)
        
        # Итоговое сообщение
        self.message_user(request, "=" * 60, messages.INFO)
        self.message_user(request, f"🎉 ЗАВЕРШЕНО: Сгенерировано {generated_count}, пропущено {skipped_count}, ошибок {len(errors)}", messages.SUCCESS if generated_count > 0 else messages.INFO)
    
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