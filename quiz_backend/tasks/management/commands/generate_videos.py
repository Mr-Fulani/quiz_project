"""
Команда для генерации видео для существующих задач.
Генерирует видео только для задач с русским переводом, у которых еще нет video_url.
"""
import logging
from django.core.management.base import BaseCommand
from tasks.models import Task, TaskTranslation
from tasks.services.video_generation_service import generate_video_for_task
from django.conf import settings

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Генерирует видео для задач без video_url (только для русского языка)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--task-id',
            type=int,
            help='ID конкретной задачи для генерации видео',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Генерировать видео для всех подходящих задач',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='Максимальное количество задач для обработки (по умолчанию 10)',
        )

    def handle(self, *args, **options):
        # Проверяем, включена ли генерация видео
        video_generation_enabled = getattr(settings, 'VIDEO_GENERATION_ENABLED', True)
        if not video_generation_enabled:
            self.stdout.write(self.style.WARNING('⚠️ Генерация видео отключена в настройках'))
            return

        task_id = options.get('task_id')
        generate_all = options.get('all', False)
        limit = options.get('limit', 10)

        if task_id:
            # Генерируем видео для конкретной задачи
            try:
                task = Task.objects.get(pk=task_id)
                self._generate_video_for_task(task)
            except Task.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'❌ Задача с ID {task_id} не найдена'))
                return
        elif generate_all:
            # Генерируем видео для всех подходящих задач
            tasks = Task.objects.filter(
                video_url__isnull=True,
                translations__language='ru'
            ).distinct()[:limit]
            
            total = tasks.count()
            self.stdout.write(f'📹 Найдено задач для генерации видео: {total}')
            
            for idx, task in enumerate(tasks, 1):
                self.stdout.write(f'\n[{idx}/{total}] Обработка задачи {task.id}...')
                self._generate_video_for_task(task)
        else:
            self.stdout.write(self.style.ERROR(
                'Укажите --task-id <id> для конкретной задачи или --all для всех задач'
            ))

    def _generate_video_for_task(self, task: Task):
        """
        Генерирует видео для конкретной задачи.
        
        Args:
            task: Объект задачи Task
        """
        # Проверяем, есть ли уже видео
        if task.video_url:
            self.stdout.write(f'⚠️ Задача {task.id} уже имеет видео: {task.video_url}')
            return

        # Ищем русский перевод
        ru_translation = task.translations.filter(language='ru').first()
        if not ru_translation:
            self.stdout.write(f'⚠️ Задача {task.id} не имеет русского перевода, пропускаем')
            return

        # Получаем название темы
        topic_name = task.topic.name if task.topic else 'unknown'

        try:
            self.stdout.write(f'🎬 Генерация видео для задачи {task.id} (тема: {topic_name})...')
            
            # Генерируем видео
            video_url = generate_video_for_task(ru_translation.question, topic_name)
            
            if video_url:
                # Сохраняем URL видео
                task.video_url = video_url
                task.save(update_fields=['video_url'])
                self.stdout.write(self.style.SUCCESS(f'✅ Видео успешно создано для задачи {task.id}'))
                self.stdout.write(f'   URL: {video_url}')
            else:
                self.stdout.write(self.style.WARNING(f'⚠️ Не удалось сгенерировать видео для задачи {task.id}'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Ошибка при генерации видео для задачи {task.id}: {e}'))
            logger.error(f'Ошибка генерации видео для задачи {task.id}: {e}', exc_info=True)

