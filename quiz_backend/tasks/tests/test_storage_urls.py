"""Ссылки на файлы задач: в БД ключ файла, наружу — URL с текущим доменом хранилища."""
import importlib

from django.db import connection
from django.test import TestCase, override_settings

from tasks.models import Task
from tasks.storage_urls import to_public_url, to_storage_key
from topics.models import Topic

KEY = 'prod/tenant-a/tasks/python/images/task_1.png'


def _raw(task_id):
    with connection.cursor() as cursor:
        cursor.execute('SELECT image_url, video_urls FROM tasks WHERE id = %s', [task_id])
        return cursor.fetchone()


@override_settings(AWS_PUBLIC_MEDIA_DOMAIN='media.example.com', STORAGE_LEGACY_DOMAINS=['cdn.old.com'])
class StorageUrlsTest(TestCase):
    def setUp(self):
        self.topic = Topic.objects.create(name='Python', description='')

    def _task(self, **kwargs):
        return Task.objects.create(topic=self.topic, difficulty='easy', **kwargs)

    def test_url_of_own_storage_is_saved_as_key(self):
        task = self._task(image_url=f'https://media.example.com/{KEY}')
        self.assertEqual(_raw(task.id)[0], KEY)
        self.assertEqual(Task.objects.get(id=task.id).image_url, f'https://media.example.com/{KEY}')

    def test_domain_change_needs_no_data_change(self):
        task = self._task(image_url=f'https://media.example.com/{KEY}')
        with self.settings(AWS_PUBLIC_MEDIA_DOMAIN='files.new-site.org'):
            self.assertEqual(Task.objects.get(id=task.id).image_url, f'https://files.new-site.org/{KEY}')

    def test_legacy_domain_and_encoded_slashes_become_key(self):
        task = self._task(image_url='https://cdn.old.com/prod%2Ftenant-a%2Ftasks%2Fpython%2Fimages%2Ftask_1.png')
        self.assertEqual(_raw(task.id)[0], KEY)

    def test_external_url_is_kept(self):
        url = 'https://images.example.org/picture.png'
        task = self._task(image_url=url)
        self.assertEqual(_raw(task.id)[0], url)
        self.assertEqual(Task.objects.get(id=task.id).image_url, url)

    def test_video_urls_map(self):
        task = self._task(video_urls={'ru': f'https://media.example.com/{KEY}', 'en': ''})
        self.assertIn(f'"ru": "{KEY}"', _raw(task.id)[1])
        self.assertEqual(Task.objects.get(id=task.id).video_urls['ru'], f'https://media.example.com/{KEY}')

    def test_empty_values(self):
        task = self._task(image_url=None)
        self.assertIsNone(Task.objects.get(id=task.id).image_url)
        self.assertEqual(to_storage_key(''), '')
        self.assertEqual(to_public_url(''), '')

    def test_migration_converts_existing_rows_both_ways(self):
        task = self._task()
        with connection.cursor() as cursor:
            cursor.execute(
                'UPDATE tasks SET image_url = %s, video_urls = %s WHERE id = %s',
                [f'https://media.example.com/{KEY}', f'{{"ru": "https://cdn.old.com/{KEY}"}}', task.id],
            )
        migration = importlib.import_module('tasks.migrations.0026_task_storage_keys')
        schema_editor = type('SE', (), {'connection': connection})()

        migration._convert(to_storage_key)(None, schema_editor)
        self.assertEqual(_raw(task.id)[0], KEY)
        self.assertIn(f'"ru": "{KEY}"', _raw(task.id)[1])

        migration._convert(to_public_url)(None, schema_editor)
        self.assertEqual(_raw(task.id)[0], f'https://media.example.com/{KEY}')
