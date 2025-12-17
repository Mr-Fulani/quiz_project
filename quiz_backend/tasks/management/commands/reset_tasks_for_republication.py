"""
Django management command для сброса задач перед повторной публикацией.

Удаляет все старые ссылки на изображения и отмечает все задачи как неопубликованные,
чтобы можно было заново опубликовать их с новой генерацией картинок.
"""
import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from tasks.models import Task

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        'Удаляет все старые ссылки на изображения (image_url) и отмечает все задачи '
        'как неопубликованные (published=False) для повторной публикации с новой генерацией картинок.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Проверка без реальных изменений в БД',
        )
        parser.add_argument(
            '--task-ids',
            type=str,
            help='Список ID задач через запятую (например: 1,2,3). Если не указан, обрабатываются все задачи.',
        )
        parser.add_argument(
            '--translation-group-ids',
            type=str,
            help='Список translation_group_id через запятую. Если не указан, обрабатываются все задачи.',
        )
        parser.add_argument(
            '--clear-image-url-only',
            action='store_true',
            help='Только очистить image_url, не сбрасывать published статус',
        )
        parser.add_argument(
            '--reset-published-only',
            action='store_true',
            help='Только сбросить published статус, не очищать image_url',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        task_ids_str = options.get('task_ids')
        translation_group_ids_str = options.get('translation_group_ids')
        clear_image_url_only = options.get('clear_image_url_only', False)
        reset_published_only = options.get('reset_published_only', False)

        # Определяем, что нужно делать
        clear_image_url = not reset_published_only
        reset_published = not clear_image_url_only

        if not clear_image_url and not reset_published:
            self.stdout.write(
                self.style.ERROR('❌ Необходимо указать хотя бы одно действие (--clear-image-url-only или --reset-published-only)')
            )
            return

        # Формируем queryset
        queryset = Task.objects.all()

        # Фильтр по task_ids
        if task_ids_str:
            try:
                task_ids = [int(id.strip()) for id in task_ids_str.split(',')]
                queryset = queryset.filter(id__in=task_ids)
                self.stdout.write(
                    self.style.SUCCESS(f'📋 Фильтр по ID задач: {task_ids}')
                )
            except ValueError:
                self.stdout.write(
                    self.style.ERROR('❌ Неверный формат task_ids. Используйте: 1,2,3')
                )
                return

        # Фильтр по translation_group_ids
        if translation_group_ids_str:
            try:
                from uuid import UUID
                group_ids = [UUID(id.strip()) for id in translation_group_ids_str.split(',')]
                queryset = queryset.filter(translation_group_id__in=group_ids)
                self.stdout.write(
                    self.style.SUCCESS(f'📋 Фильтр по translation_group_id: {group_ids}')
                )
            except (ValueError, AttributeError) as e:
                self.stdout.write(
                    self.style.ERROR(f'❌ Неверный формат translation_group_ids: {e}')
                )
                return

        total_tasks = queryset.count()

        if total_tasks == 0:
            self.stdout.write(
                self.style.WARNING('⚠️ Не найдено задач для обработки')
            )
            return

        self.stdout.write('=' * 60)
        self.stdout.write(
            self.style.SUCCESS(f'📊 Найдено задач для обработки: {total_tasks}')
        )
        
        if clear_image_url:
            tasks_with_images = queryset.exclude(image_url__isnull=True).exclude(image_url='').count()
            self.stdout.write(f'   📷 Задач с изображениями: {tasks_with_images}')
        
        if reset_published:
            published_tasks = queryset.filter(published=True).count()
            self.stdout.write(f'   ✅ Опубликованных задач: {published_tasks}')

        self.stdout.write('=' * 60)

        if dry_run:
            self.stdout.write(
                self.style.WARNING('🔍 РЕЖИМ ПРОВЕРКИ (dry-run) - изменения не будут сохранены')
            )
            self.stdout.write('=' * 60)

        # Подтверждение
        if not dry_run:
            confirm = input(
                f'\n⚠️  Вы уверены, что хотите обработать {total_tasks} задач? '
                f'(yes/no): '
            )
            if confirm.lower() not in ['yes', 'y', 'да', 'д']:
                self.stdout.write(self.style.WARNING('❌ Операция отменена'))
                return

        # Обработка
        updated_count = 0
        cleared_images_count = 0
        reset_published_count = 0

        try:
            with transaction.atomic():
                for task in queryset.iterator(chunk_size=100):
                    updated = False
                    update_fields = []

                    # Очистка image_url
                    if clear_image_url and task.image_url:
                        old_url = task.image_url
                        task.image_url = None
                        update_fields.append('image_url')
                        cleared_images_count += 1
                        updated = True
                        if not dry_run:
                            logger.info(f'Очищен image_url для задачи {task.id}: {old_url}')

                    # Сброс published
                    if reset_published and task.published:
                        task.published = False
                        task.publish_date = None
                        task.message_id = None
                        task.error = False
                        update_fields.extend(['published', 'publish_date', 'message_id', 'error'])
                        reset_published_count += 1
                        updated = True
                        if not dry_run:
                            logger.info(f'Сброшен статус публикации для задачи {task.id}')

                    if updated:
                        if not dry_run:
                            task.save(update_fields=update_fields)
                        updated_count += 1

                if dry_run:
                    # В dry-run режиме откатываем транзакцию
                    raise transaction.TransactionManagementError('Dry run mode')

        except transaction.TransactionManagementError:
            # Это ожидаемо в dry-run режиме
            pass

        # Итоговый отчет
        self.stdout.write('=' * 60)
        if dry_run:
            self.stdout.write(
                self.style.WARNING('🔍 РЕЖИМ ПРОВЕРКИ - изменения НЕ были сохранены')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('✅ Операция завершена успешно!')
            )
        
        self.stdout.write('=' * 60)
        self.stdout.write(
            self.style.SUCCESS(f'📊 Итоговая статистика:')
        )
        self.stdout.write(f'   📝 Всего обработано задач: {updated_count} из {total_tasks}')
        
        if clear_image_url:
            self.stdout.write(f'   🗑️  Очищено image_url: {cleared_images_count}')
        
        if reset_published:
            self.stdout.write(f'   🔄 Сброшен статус published: {reset_published_count}')

        self.stdout.write('=' * 60)
        
        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    '\n🎯 Теперь вы можете заново опубликовать задачи через Django Admin.\n'
                    '   При публикации изображения будут автоматически сгенерированы.'
                )
            )

