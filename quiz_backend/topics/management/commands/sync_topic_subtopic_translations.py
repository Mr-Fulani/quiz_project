import json

from django.core.management.base import BaseCommand, CommandError

from tasks.services.task_import_service import (
    _find_subtopic,
    _find_topic,
    _resolve_base_name_and_translations,
    _upsert_subtopic_translations,
    _upsert_topic_translations,
)


class Command(BaseCommand):
    help = 'Синхронизирует переводы тем и подтем из JSON без повторного импорта задач'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            required=True,
            help='Путь к JSON файлу с задачами'
        )
        parser.add_argument(
            '--tenant-slug',
            type=str,
            required=False,
            help='Slug тенанта для точного поиска тем'
        )
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Применить изменения. Без флага команда работает в режиме dry-run.'
        )

    def handle(self, *args, **options):
        file_path = options['file']
        tenant_slug = options.get('tenant_slug')
        apply_changes = options['apply']

        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
        except FileNotFoundError as exc:
            raise CommandError(f'Файл не найден: {file_path}') from exc
        except json.JSONDecodeError as exc:
            raise CommandError(f'Ошибка парсинга JSON: {exc}') from exc

        tenant = None
        if tenant_slug:
            from tenants.models import Tenant
            tenant = Tenant.objects.filter(slug=tenant_slug).first()
            if not tenant:
                raise CommandError(f'Тенант не найден: {tenant_slug}')

        tasks_data = data.get('tasks', [])
        self.stdout.write(self.style.SUCCESS(
            f"Найдено задач в JSON: {len(tasks_data)}. Режим: {'APPLY' if apply_changes else 'DRY-RUN'}"
        ))

        updated_topics = 0
        updated_subtopics = 0

        for index, task_data in enumerate(tasks_data, start=1):
            topic_name, topic_translations = _resolve_base_name_and_translations(
                task_data.get('topic'),
                task_data.get('topic_translations'),
            )
            subtopic_name, subtopic_translations = _resolve_base_name_and_translations(
                task_data.get('subtopic'),
                task_data.get('subtopic_translations'),
            )

            topic = _find_topic(tenant, topic_name, topic_translations)
            if not topic:
                self.stdout.write(self.style.WARNING(
                    f"[{index}] Тема не найдена: {topic_name!r}"
                ))
                continue

            if topic_translations:
                self.stdout.write(
                    f"[{index}] Тема #{topic.id} '{topic.name}' -> языки: {', '.join(sorted(topic_translations.keys()))}"
                )
                if apply_changes:
                    _upsert_topic_translations(
                        topic=topic,
                        topic_translations=topic_translations,
                        fallback_name=topic.name,
                        fallback_description=topic.description,
                        tenant_default_language=getattr(tenant, 'default_language', None),
                    )
                    updated_topics += 1

            if not subtopic_name and not subtopic_translations:
                continue

            subtopic = _find_subtopic(topic, subtopic_name, subtopic_translations)
            if not subtopic:
                self.stdout.write(self.style.WARNING(
                    f"[{index}] Подтема не найдена для темы '{topic.name}': {subtopic_name!r}"
                ))
                continue

            if subtopic_translations:
                self.stdout.write(
                    f"[{index}] Подтема #{subtopic.id} '{subtopic.name}' -> языки: {', '.join(sorted(subtopic_translations.keys()))}"
                )
                if apply_changes:
                    _upsert_subtopic_translations(
                        subtopic=subtopic,
                        subtopic_translations=subtopic_translations,
                        fallback_name=subtopic.name,
                        tenant_default_language=getattr(tenant, 'default_language', None),
                    )
                    updated_subtopics += 1

        if apply_changes:
            self.stdout.write(self.style.SUCCESS(
                f'Готово. Обновлено тем: {updated_topics}, подтем: {updated_subtopics}'
            ))
        else:
            self.stdout.write(self.style.WARNING(
                'Это dry-run. Для применения изменений запустите команду с флагом --apply.'
            ))
