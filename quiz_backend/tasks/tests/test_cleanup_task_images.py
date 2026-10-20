"""Очистка хранилища: остаются только картинки английских задач."""
from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from tasks.models import Task, TaskTranslation
from topics.models import Topic

EN_IMAGE = 'prod/t/tasks/python/images/python_en_1.png'
RU_IMAGE = 'prod/t/tasks/python/images/python_ru_2.png'
ORPHAN_IMAGE = 'prod/images/old_task.png'
VIDEO = 'prod/videos/task_1.mp4'
ORPHAN_VIDEO = 'prod/videos/old.mp4'
JSON_FILE = 'prod/t/tasks/json/import.json'


def fake_client():
    client = MagicMock()
    page = {'Contents': [{'Key': key, 'Size': 1024} for key in
                         (EN_IMAGE, RU_IMAGE, ORPHAN_IMAGE, VIDEO, ORPHAN_VIDEO, JSON_FILE)]}
    client.get_paginator.return_value.paginate.return_value = [page]
    client.delete_objects.return_value = {}
    return client


@override_settings(AWS_PUBLIC_MEDIA_DOMAIN='media.example.com', AWS_STORAGE_BUCKET_NAME='bucket',
                   R2_ENVIRONMENT_PREFIX='prod')
class CleanupTaskImagesTest(TestCase):
    def setUp(self):
        topic = Topic.objects.create(name='Python', description='')
        self.en = Task.objects.create(topic=topic, difficulty='easy', image_url=EN_IMAGE, video_urls={'en': VIDEO})
        self.ru = Task.objects.create(topic=topic, difficulty='easy', image_url=RU_IMAGE)
        for task, language in ((self.en, 'en'), (self.ru, 'ru')):
            TaskTranslation.objects.create(task=task, language=language, question='q', answers=['a'], correct_answer='a')
        self.client_mock = fake_client()
        patcher = patch('tasks.management.commands.cleanup_task_images._make_r2_client', return_value=self.client_mock)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_command(self, *args):
        out = StringIO()
        call_command('cleanup_task_images', *args, stdout=out)
        return out.getvalue()

    def deleted_keys(self):
        return [o['Key'] for call in self.client_mock.delete_objects.call_args_list
                for o in call.kwargs['Delete']['Objects']]

    def test_dry_run_deletes_nothing(self):
        output = self.run_command()
        self.assertIn('К удалению: 2 файлов', output)
        self.client_mock.delete_objects.assert_not_called()
        self.ru.refresh_from_db()
        self.assertTrue(self.ru.image_url)

    def test_apply_keeps_english_images(self):
        self.run_command('--apply')
        self.assertEqual(sorted(self.deleted_keys()), sorted([RU_IMAGE, ORPHAN_IMAGE]))
        self.ru.refresh_from_db()
        self.en.refresh_from_db()
        self.assertIsNone(self.ru.image_url)
        self.assertEqual(self.en.image_url, f'https://media.example.com/{EN_IMAGE}')
        self.client_mock.get_paginator.return_value.paginate.assert_called_with(Bucket='bucket', Prefix='prod/')

    def test_orphan_videos_only_when_asked(self):
        self.run_command('--apply', '--orphan-videos')
        self.assertIn(ORPHAN_VIDEO, self.deleted_keys())
        self.assertNotIn(VIDEO, self.deleted_keys())
        self.assertNotIn(JSON_FILE, self.deleted_keys())
