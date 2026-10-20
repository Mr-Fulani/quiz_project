"""
Публикация/генерация из админки задач идёт через Celery: экшен только ставит задачу в очередь,
воркер публикует ботом тенанта задачи (tenants.scoping.bot_token_for).
"""
import uuid
from unittest.mock import MagicMock, patch

from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import CustomUser
from platforms.models import TelegramGroup
from tasks.models import Task, TaskTranslation
from tasks.tasks import (
    generate_task_images_async,
    publish_tasks_to_social_async,
    publish_tasks_to_telegram_async,
)
from tenants.models import Tenant
from topics.models import Subtopic, Topic


class PublicationTestMixin:
    def setUp(self):
        self.tenant = Tenant.objects.create(
            slug='pub-a', name='A', domain='pub-a.example.com', site_name='A', bot_token='111:tenant-a',
        )
        self.topic = Topic.objects.create(name='Python', tenant=self.tenant)
        self.subtopic = Subtopic.objects.create(name='Basics', topic=self.topic)

    def make_task(self, language='en', group_id=None, image_url='https://cdn.example.com/img.png'):
        task = Task.objects.create(
            tenant=self.tenant, topic=self.topic, subtopic=self.subtopic, difficulty='easy',
            translation_group_id=group_id or uuid.uuid4(), image_url=image_url,
        )
        TaskTranslation.objects.create(
            task=task, language=language, question=f'Question {language}?',
            answers=['a', 'b', 'c'], correct_answer='a',
        )
        return task


@override_settings(ALLOWED_HOSTS=['*'])
class TaskAdminPublicationActionsTests(PublicationTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.admin_user = CustomUser.objects.create_superuser(
            username='pub_admin', email='pub@example.com', password='password123'
        )
        self.client.force_login(self.admin_user)
        self.url = reverse('admin:tasks_task_changelist')

    def run_action(self, action, tasks, **extra):
        data = {'action': action, ACTION_CHECKBOX_NAME: [task.id for task in tasks], **extra}
        return self.client.post(self.url, data, HTTP_HOST='pub-a.example.com', follow=True)

    @patch('tasks.services.telegram_service.publish_task_to_telegram')
    @patch('tasks.tasks.publish_tasks_to_telegram_async.delay')
    def test_publish_to_telegram_enqueues_related_translations(self, mock_delay, mock_publish):
        mock_delay.return_value = MagicMock(id='celery-1')
        group_id = uuid.uuid4()
        en_task = self.make_task('en', group_id)
        ru_task = self.make_task('ru', group_id)
        self.make_task('en')  # чужая группа переводов — не публикуется

        response = self.run_action('publish_to_telegram', [en_task])

        mock_delay.assert_called_once()
        self.assertCountEqual(mock_delay.call_args.args[0], [en_task.id, ru_task.id])
        mock_publish.assert_not_called()
        self.assertContains(response, 'Поставлено в очередь 2 задач')

    def test_import_form_preselects_tenant_image_theme(self):
        self.tenant.image_theme = Tenant.IMAGE_THEME_ISLAMIC
        self.tenant.save()

        response = self.client.get(reverse('admin:tasks_task_import_json'), HTTP_HOST='pub-a.example.com')

        self.assertContains(response, '<option value="islamic" selected>', html=False)
        self.assertNotContains(response, '<option value="code" selected>', html=False)

    @patch('tasks.tasks.generate_task_images_async.delay')
    def test_generate_images_enqueues_selected_tasks_with_theme(self, mock_delay):
        mock_delay.return_value = MagicMock(id='celery-2')
        tasks = [self.make_task(image_url=None), self.make_task(image_url=None)]

        response = self.run_action('generate_images', tasks, post='yes', image_theme='islamic')

        mock_delay.assert_called_once()
        task_ids, theme = mock_delay.call_args.args
        self.assertCountEqual(task_ids, [task.id for task in tasks])
        self.assertEqual(theme, 'islamic')
        self.assertContains(response, 'Поставлено в очередь 2 задач на генерацию изображений')

    @patch('tasks.tasks.publish_tasks_to_social_async.delay')
    def test_publish_to_platform_enqueues_with_platform(self, mock_delay):
        mock_delay.return_value = MagicMock(id='celery-3')
        task = self.make_task()

        self.run_action('publish_to_pinterest', [task])

        mock_delay.assert_called_once_with([task.id], platform='pinterest', require_video=False)

    @patch('tasks.tasks.publish_tasks_to_social_async.delay')
    def test_auto_reshare_enqueues_reels_requiring_video(self, mock_delay):
        mock_delay.return_value = MagicMock(id='celery-4')
        task = self.make_task()

        self.run_action('publish_with_auto_reshare', [task])

        mock_delay.assert_called_once_with([task.id], platform='instagram_reels', require_video=True)


def telegram_ok_response(*args, **kwargs):
    response = MagicMock(status_code=200)
    response.json.return_value = {'ok': True, 'result': {'message_id': 42, 'poll': {'id': 'poll-1'}}}
    return response


@patch('time.sleep')
@patch('tasks.tasks._pause_between_task_publications')
class PublishTasksToTelegramAsyncTests(PublicationTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        TelegramGroup.objects.create(
            tenant=self.tenant, group_name='Python EN', group_id=-1001, topic_id=self.topic, language='en',
        )

    @patch('tasks.services.telegram_service.requests.post', side_effect=telegram_ok_response)
    def test_publishes_with_tenant_bot_token_and_sets_flags(self, mock_post, mock_pause, _):
        task = self.make_task('en')

        result = publish_tasks_to_telegram_async(task_ids=[task.id])

        self.assertEqual(result['published'], 1)
        urls = [call.args[0] for call in mock_post.call_args_list]
        self.assertTrue(urls)
        self.assertTrue(all('/bot111:tenant-a/' in url for url in urls), urls)
        task.refresh_from_db()
        self.assertTrue(task.published_telegram)
        self.assertTrue(task.published)
        self.assertFalse(task.error)
        self.assertEqual(task.message_id, 42)
        mock_pause.assert_not_called()  # пауза только между задачами

    @patch('tasks.tasks.publish_task_to_telegram', return_value={'success': True, 'errors': [], 'detailed_logs': []})
    def test_pauses_between_tasks_in_worker(self, mock_publish, mock_pause, _):
        tasks = [self.make_task('en'), self.make_task('en')]

        publish_tasks_to_telegram_async(task_ids=[task.id for task in tasks])

        self.assertEqual([call.kwargs['task'].id for call in mock_publish.call_args_list], [t.id for t in tasks])
        mock_pause.assert_called_once()

    @patch('tasks.services.social_image.generate_image_for_task')
    @patch('tasks.tasks.publish_task_to_telegram', return_value={'success': True, 'errors': [], 'detailed_logs': []})
    def test_publishes_without_image_and_does_not_generate_one(self, mock_publish, mock_generate, *_):
        # Вопрос публикуется текстом: картинка для Telegram не нужна и не генерируется
        task = self.make_task('en', image_url=None)

        publish_tasks_to_telegram_async(task_ids=[task.id])

        mock_publish.assert_called_once()
        mock_generate.assert_not_called()
        task.refresh_from_db()
        self.assertTrue(task.published)
        self.assertFalse(task.image_url)

    @patch('config.tasks.send_webhooks_async.delay')
    @patch('tasks.tasks.publish_task_to_telegram', return_value={'success': True, 'errors': [], 'detailed_logs': []})
    def test_sends_regular_webhooks_after_publication(self, mock_publish, mock_webhooks, *_):
        from webhooks.models import Webhook
        Webhook.objects.create(tenant=self.tenant, url='https://hook.example.com', webhook_type='regular', is_active=True)
        task = self.make_task('en')

        publish_tasks_to_telegram_async(task_ids=[task.id])

        mock_webhooks.assert_called_once()
        self.assertEqual(mock_webhooks.call_args.kwargs['task_ids'], [task.id])


class OtherPublicationTasksTests(PublicationTestMixin, TestCase):
    @patch('tasks.services.social_image.upload_image_to_s3', return_value='https://cdn.example.com/gen.png')
    @patch('tasks.services.social_image.generate_image_for_task', return_value=object())
    def test_generate_task_images_saves_url(self, mock_generate, mock_upload):
        task = self.make_task(image_url=None)

        result = generate_task_images_async(task_ids=[task.id], image_theme='islamic')

        self.assertEqual(result['generated'], 1)
        self.assertEqual(mock_generate.call_args.kwargs['theme'], 'islamic')
        task.refresh_from_db()
        self.assertEqual(task.image_url, 'https://cdn.example.com/gen.png')

    @patch('tasks.services.social_image.generate_image_for_task')
    def test_generate_task_images_skips_non_english(self, mock_generate):
        task = self.make_task('ru', image_url=None)

        result = generate_task_images_async(task_ids=[task.id])

        self.assertEqual(result['generated'], 0)
        mock_generate.assert_not_called()

    @patch('tasks.services.social_media_service.publish_to_platform', return_value={'success': True})
    def test_publish_to_platform_marks_published(self, mock_platform):
        task = self.make_task()

        result = publish_tasks_to_social_async(task_ids=[task.id], platform='pinterest')

        self.assertEqual(result['published'], 1)
        self.assertEqual(mock_platform.call_args.args[2], 'pinterest')
        task.refresh_from_db()
        self.assertTrue(task.published)
