from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import models


OLD_PREFIX = 'https://my-quiz-images.s3.eu-north-1.amazonaws.com/'
NEW_PREFIX = 'https://d2010igkoonfw4.cloudfront.net/'


class Command(BaseCommand):
    """
    Команда для массовой замены ссылок на изображения с S3-хоста на CloudFront.
    """

    help = (
        'Перезаписывает все поля с текстовыми ссылками, содержащими S3-домен, '
        'на соответствующий CloudFront-домен.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показывает количество затронутых записей, но не вносит изменения.'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        total_models = 0
        total_records = 0
        total_replacements = 0

        for model in apps.get_models():
            if model._meta.proxy or not model._meta.managed:
                continue

            text_fields = [
                field for field in model._meta.get_fields()
                if isinstance(field, (models.CharField, models.TextField, models.URLField))
                and not getattr(field, 'many_to_many', False)
                and not getattr(field, 'one_to_many', False)
            ]

            if not text_fields:
                continue

            queryset = model.objects.all()
            model_updated = False

            for instance in queryset.iterator(chunk_size=200):
                updated_fields = []
                replacements_in_instance = 0

                for field in text_fields:
                    value = getattr(instance, field.name, '')
                    if isinstance(value, str) and OLD_PREFIX in value:
                        new_value = value.replace(OLD_PREFIX, NEW_PREFIX)
                        if new_value != value:
                            setattr(instance, field.name, new_value)
                            updated_fields.append(field.name)
                            replacements_in_instance += value.count(OLD_PREFIX)

                if updated_fields:
                    model_updated = True
                    total_records += 1
                    total_replacements += replacements_in_instance
                    if not dry_run:
                        instance.save(update_fields=updated_fields)

            if model_updated:
                total_models += 1
                status = 'DRY-RUN' if dry_run else 'ОБНОВЛЕНО'
                self.stdout.write(f'{status}: {model._meta.label} ({len(text_fields)} полей)')

        summary_prefix = 'ПРОВЕРЕНО' if dry_run else 'ГОТОВО'
        self.stdout.write(
            self.style.SUCCESS(
                f'{summary_prefix}: моделей {total_models}, записей {total_records}, '
                f'замен {total_replacements}.'
            )
        )

