from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from accounts.models import MiniAppUser
from accounts.tests.test_telegram_webapp_auth import make_init_data
from tasks.models import MiniAppTaskStatistics, Task, TaskTranslation
from tenants.middleware import clear_tenant_cache
from tenants.models import Tenant
from topics.models import Subtopic, Topic

BOT_TOKEN = '444444:topic-tenant-token'


@override_settings(ALLOWED_HOSTS=['*'])
class TopicSubtopicsStatsTests(TestCase):
    def setUp(self):
        clear_tenant_cache()
        self.tenant = Tenant.objects.create(
            slug='ts-a', name='A', domain='ts-a.example.com', mini_app_domain='mini.ts-a.example.com', site_name='A',
            bot_token=BOT_TOKEN,
        )
        self.other_tenant = Tenant.objects.create(slug='ts-b', name='B', domain='ts-b.example.com', site_name='B')
        self.topic = Topic.objects.create(tenant=self.tenant, name='Python')
        self.user = MiniAppUser.objects.create(tenant=self.tenant, telegram_id=8001, username='u')
        self.host = {
            'HTTP_HOST': 'mini.ts-a.example.com',
            'HTTP_X_TELEGRAM_INIT_DATA': make_init_data(BOT_TOKEN, {'id': 8001}),
        }

    def add_subtopic(self, name, difficulties):
        subtopic = Subtopic.objects.create(topic=self.topic, name=name)
        tasks = []
        for difficulty in difficulties:
            task = Task.objects.create(
                tenant=self.tenant, topic=self.topic, subtopic=subtopic, difficulty=difficulty, published=True
            )
            TaskTranslation.objects.create(task=task, language='en', question='Q?', answers=['a'], correct_answer='a')
            tasks.append(task)
        return subtopic, tasks

    def fetch(self):
        return self.client.get(
            f'/api/{self.topic.id}/subtopics/', {'language': 'en', 'telegram_id': 8001}, **self.host
        )

    @staticmethod
    def app_queries(context):
        return [q for q in context.captured_queries if 'silk_' not in q['sql'] and 'SAVEPOINT' not in q['sql']]

    def test_counts_and_completion(self):
        subtopic, (easy, hard) = self.add_subtopic('Functions', ['easy', 'hard'])
        MiniAppTaskStatistics.objects.create(mini_app_user=self.user, task=easy, successful=True)
        # Решение того же telegram_id в другом тенанте не считается
        other_user = MiniAppUser.objects.create(tenant=self.other_tenant, telegram_id=8001, username='u2')
        MiniAppTaskStatistics.objects.create(mini_app_user=other_user, task=hard, successful=True)

        item = {row['id']: row for row in self.fetch().json()}[subtopic.id]
        self.assertEqual(item['questions_count'], 2)
        self.assertEqual(item['difficulty_counts'], {'easy': 1, 'medium': 0, 'hard': 1})
        self.assertEqual(item['solved_counts'], {'easy': 1, 'medium': 0, 'hard': 0})
        self.assertFalse(item['is_completed'])

        MiniAppTaskStatistics.objects.create(mini_app_user=self.user, task=hard, successful=True)
        item = {row['id']: row for row in self.fetch().json()}[subtopic.id]
        self.assertTrue(item['is_completed'])

        # Без подписанного initData прогресс по telegram_id не раскрывается
        anonymous = self.client.get(
            f'/api/{self.topic.id}/subtopics/', {'language': 'en', 'telegram_id': 8001},
            HTTP_HOST='mini.ts-a.example.com',
        ).json()
        self.assertEqual(anonymous[0]['solved_counts'], {'easy': 0, 'medium': 0, 'hard': 0})

    def test_query_count_does_not_grow_with_number_of_subtopics(self):
        self.add_subtopic('S1', ['easy'])
        self.fetch()  # прогрев кэша тенантов
        with CaptureQueriesContext(connection) as small:
            self.fetch()
        for index in range(4):
            self.add_subtopic(f'S{index + 2}', ['easy', 'medium'])
        with CaptureQueriesContext(connection) as large:
            response = self.fetch()
        self.assertEqual(len(response.json()), 5)
        self.assertEqual(len(self.app_queries(large)), len(self.app_queries(small)))
