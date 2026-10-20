"""
Очистка хранилища (R2/S3) от ненужных картинок задач.

Картинки нужны только английским задачам (для соцсетей, см. tasks/services/social_image.py).
Удаляются картинки, на которые не ссылается ни одна английская задача: картинки неанглийских задач
(ссылка у задачи очищается) и файлы, на которые не ссылается никто. С --orphan-videos — ещё видео,
на которые не ссылается ни одна задача.

    python manage.py cleanup_task_images                  # пробный прогон: что будет удалено
    python manage.py cleanup_task_images --apply          # удалить
    python manage.py cleanup_task_images --prefix dev     # другая папка окружения
"""
from collections import Counter

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from tasks.models import Task
from tasks.services.s3_service import _make_r2_client
from tasks.services.social_image import SOCIAL_IMAGE_LANGUAGES
from tasks.storage_urls import to_storage_key

DELETE_BATCH = 1000  # максимум ключей в одном запросе DeleteObjects


def _folder(key):
    parts = key.split('/')
    return '/'.join(parts[:2] + ['…', parts[-2]]) if len(parts) > 4 else '/'.join(parts[:-1])


class Command(BaseCommand):
    help = 'Удаляет из хранилища картинки, не нужные английским задачам (по умолчанию — пробный прогон)'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Удалить (без флага — только показать)')
        parser.add_argument('--prefix', help='Папка окружения в бакете (по умолчанию R2_ENVIRONMENT_PREFIX)')
        parser.add_argument('--orphan-videos', action='store_true',
                            help='Удалить и видео, на которые не ссылается ни одна задача')

    def handle(self, *args, **options):
        bucket = settings.AWS_STORAGE_BUCKET_NAME
        prefix = (options['prefix'] or getattr(settings, 'R2_ENVIRONMENT_PREFIX', None) or 'prod').strip('/') + '/'
        client = _make_r2_client()

        objects = self._list_objects(client, bucket, prefix)
        if not objects:
            raise CommandError(f'В бакете {bucket} нет файлов в папке {prefix} — нечего чистить')

        image_refs, video_refs = self._references()
        keep_languages = set(SOCIAL_IMAGE_LANGUAGES)

        delete_keys, clear_task_ids = [], set()
        for key in objects:
            if '/images/' in key:
                tasks = image_refs.get(key, {})
                if not any(langs & keep_languages for langs in tasks.values()):
                    delete_keys.append(key)
                    clear_task_ids.update(tasks)
            elif '/videos/' in key and options['orphan_videos'] and key not in video_refs:
                delete_keys.append(key)

        self._report(objects, delete_keys, clear_task_ids, prefix)
        if not options['apply']:
            self.stdout.write(self.style.WARNING('Пробный прогон: ничего не удалено. Для удаления — --apply'))
            return

        # Сначала ссылки в базе (чтобы при сбое не осталось ссылок на удалённые файлы), потом файлы
        cleared = Task.objects.filter(id__in=clear_task_ids).update(image_url=None)
        deleted, errors = 0, []
        for start in range(0, len(delete_keys), DELETE_BATCH):
            batch = delete_keys[start:start + DELETE_BATCH]
            response = client.delete_objects(
                Bucket=bucket, Delete={'Objects': [{'Key': key} for key in batch], 'Quiet': True},
            )
            batch_errors = response.get('Errors', [])
            errors.extend(batch_errors)
            deleted += len(batch) - len(batch_errors)

        self.stdout.write(self.style.SUCCESS(f'Удалено файлов: {deleted}; ссылок у задач очищено: {cleared}'))
        for error in errors[:10]:
            self.stdout.write(self.style.ERROR(f"  ❌ {error.get('Key')}: {error.get('Message')}"))

    @staticmethod
    def _list_objects(client, bucket, prefix):
        objects = {}
        for page in client.get_paginator('list_objects_v2').paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get('Contents', []):
                objects[obj['Key']] = obj['Size']
        return objects

    @staticmethod
    def _references():
        """Ключи картинок → {id задачи: языки её переводов}; множество ключей видео."""
        image_refs, video_refs = {}, set()
        for task in Task.objects.prefetch_related('translations'):
            languages = {t.language for t in task.translations.all()}
            if task.image_url:
                image_refs.setdefault(to_storage_key(task.image_url), {})[task.id] = languages
            for url in [task.video_url, *(task.video_urls or {}).values()]:
                if url:
                    video_refs.add(to_storage_key(url))
        return image_refs, video_refs

    def _report(self, objects, delete_keys, clear_task_ids, prefix):
        delete_size = sum(objects[key] for key in delete_keys)
        by_folder = Counter(_folder(key) for key in delete_keys)
        self.stdout.write(f'Папка {prefix}: файлов {len(objects)}, {sum(objects.values()) / 1024 / 1024:.1f} МБ')
        self.stdout.write(f'К удалению: {len(delete_keys)} файлов, {delete_size / 1024 / 1024:.1f} МБ; '
                          f'у {len(clear_task_ids)} задач будет очищена ссылка на картинку')
        for folder, count in by_folder.most_common(15):
            self.stdout.write(f'  {count:5d}  {folder}')
