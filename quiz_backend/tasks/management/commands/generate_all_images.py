"""
Генерация картинок задач для соцсетей — только для английских задач (см. tasks/services/social_image.py).

    python manage.py generate_all_images --dry-run
    python manage.py generate_all_images --task-ids 12,15 --force
    python manage.py generate_all_images --tenant quiz-code --limit 20
"""
import time

from django.core.management.base import BaseCommand
from django.db.models import Q

from tasks.models import Task
from tasks.services.social_image import SOCIAL_IMAGE_LANGUAGES, generate_task_image


class Command(BaseCommand):
    help = 'Генерирует картинки для соцсетей у английских задач (по умолчанию — только у задач без картинки)'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Показать, что будет сделано, без генерации')
        parser.add_argument('--task-ids', help='ID задач через запятую')
        parser.add_argument('--tenant', help='Slug тенанта')
        parser.add_argument('--force', action='store_true', help='Перегенерировать и существующие картинки')
        parser.add_argument('--limit', type=int, help='Обработать не больше N задач')
        parser.add_argument('--pause', type=float, default=0.5, help='Пауза между задачами, сек (по умолчанию 0.5)')

    def handle(self, *args, **options):
        tasks = (
            Task.objects.filter(translations__language__in=SOCIAL_IMAGE_LANGUAGES)
            .select_related('topic', 'subtopic', 'tenant').distinct().order_by('id')
        )
        if options['task_ids']:
            tasks = tasks.filter(id__in=[int(x) for x in options['task_ids'].split(',') if x.strip()])
        if options['tenant']:
            tasks = tasks.filter(tenant__slug=options['tenant'])
        if not options['force']:
            tasks = tasks.filter(Q(image_url__isnull=True) | Q(image_url=''))
        if options['limit']:
            tasks = tasks[:options['limit']]

        tasks = list(tasks)
        self.stdout.write(f'Задач к обработке: {len(tasks)}')
        if options['dry_run']:
            for task in tasks:
                self.stdout.write(f'  #{task.id} {task.topic.name} ({task.tenant.slug if task.tenant else "без тенанта"})')
            return

        done, errors = 0, []
        for task in tasks:
            translation = task.translations.filter(language__in=SOCIAL_IMAGE_LANGUAGES).first()
            error = generate_task_image(task, translation)
            if error:
                errors.append(error)
                self.stdout.write(self.style.ERROR(f'  ❌ {error}'))
            else:
                done += 1
                self.stdout.write(self.style.SUCCESS(f'  ✅ #{task.id}'))
            time.sleep(options['pause'])

        self.stdout.write(self.style.SUCCESS(f'Готово: {done}, ошибок: {len(errors)}'))
