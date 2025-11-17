from django.core.management.base import BaseCommand
from django.db import transaction
from topics.models import Subtopic
from topics.services.normalization_service import build_subtopic_groups
from topics.utils import normalize_subtopic_name
from tasks.models import Task


class Command(BaseCommand):
    help = (
        'Нормализует названия подтем и объединяет дубликаты внутри одной темы. '
        'По умолчанию работает в режиме dry-run.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Применить изменения к базе (по умолчанию только отчет).',
        )

    def handle(self, *args, **options):
        apply_changes = options['apply']
        groups = build_subtopic_groups()

        if not groups:
            self.stdout.write(self.style.SUCCESS('Дубликаты подтем не обнаружены.'))
            return

        self.stdout.write(
            self.style.WARNING(
                f'Найдено групп с потенциальными дубликатами: {len(groups)}',
            )
        )
        summary = []

        if not apply_changes:
            for group in groups:
                summary.append({
                    'topic_id': group.topic_id,
                    'normalized_name': group.normalized_name,
                    'canonical': f'{group.canonical.id}:{group.canonical.name}',
                    'duplicates': [
                        f'{dup.id}:{dup.name}' for dup in group.duplicates
                    ],
                })

            for item in summary:
                self.stdout.write(
                    f"[DRY-RUN] Тема={item['topic_id']} → {item['canonical']} "
                    f"заменит {len(item['duplicates'])} дублей ({', '.join(item['duplicates'])})"
                )
            self.stdout.write(
                self.style.WARNING('Изменения не применены (режим dry-run).')
            )
            return

        affected_tasks = 0
        removed_subtopics = 0

        with transaction.atomic():
            for group in groups:
                canonical = group.canonical
                normalized_name = normalize_subtopic_name(canonical.name)
                if canonical.name != normalized_name:
                    canonical.name = normalized_name
                    canonical.save(update_fields=['name'])

                for duplicate in group.duplicates:
                    updated = Task.objects.filter(subtopic=duplicate).update(
                        subtopic=canonical,
                    )
                    affected_tasks += updated
                    duplicate.delete()
                    removed_subtopics += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Нормализация завершена: обновлено задач={affected_tasks}, '
                f'удалено подтем={removed_subtopics}.'
            )
        )

