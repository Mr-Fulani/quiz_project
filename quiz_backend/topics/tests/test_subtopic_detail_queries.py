from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from accounts.models import MiniAppUser
from tasks.models import MiniAppTaskStatistics, Task, TaskTranslation
from tenants.middleware import clear_tenant_cache
from tenants.models import Tenant
from topics.models import Subtopic, Topic


@override_settings(ALLOWED_HOSTS=['*'])
class SubtopicDetailSimpleTests(TestCase):
    def setUp(self):
        clear_tenant_cache()
        self.tenant = Tenant.objects.create(
            slug='sd-a', name='A', domain='sd-a.example.com', mini_app_domain='mini.sd-a.example.com', site_name='A'
        )
        self.other_tenant = Tenant.objects.create(slug='sd-b', name='B', domain='sd-b.example.com', site_name='B')
        self.topic = Topic.objects.create(tenant=self.tenant, name='Python')
        self.subtopic = Subtopic.objects.create(topic=self.topic, name='Functions')
        self.user = MiniAppUser.objects.create(tenant=self.tenant, telegram_id=7001, username='u')
        self.host = {'HTTP_HOST': 'mini.sd-a.example.com'}

    def add_tasks(self, count):
        tasks = []
        for i in range(count):
            task = Task.objects.create(
                tenant=self.tenant, topic=self.topic, subtopic=self.subtopic, difficulty='easy', published=True
            )
            TaskTranslation.objects.create(
                task=task, language='en', question=f'Q{i}?', answers=['a', 'b', 'c'], correct_answer='a'
            )
            tasks.append(task)
        return tasks

    def fetch(self):
        return self.client.get(
            f'/api/subtopics/{self.subtopic.id}/', {'language': 'en', 'telegram_id': 7001}, **self.host
        )

    @staticmethod
    def app_queries(context):
        # Без служебных запросов профилировщика silk (DEBUG) и savepoint'ов
        return [
            q['sql'] for q in context.captured_queries
            if 'silk_' not in q['sql'] and 'SAVEPOINT' not in q['sql']
        ]

    def test_query_count_does_not_grow_with_number_of_tasks(self):
        self.add_tasks(2)
        self.fetch()  # прогрев кэша тенантов
        with CaptureQueriesContext(connection) as small:
            self.assertEqual(self.fetch().status_code, 200)
        self.add_tasks(5)
        with CaptureQueriesContext(connection) as large:
            response = self.fetch()
        self.assertEqual(len(response.json()['results']), 7)
        self.assertEqual(len(self.app_queries(large)), len(self.app_queries(small)))

    def test_solved_flags_and_completed_count(self):
        first, second = self.add_tasks(2)
        MiniAppTaskStatistics.objects.create(mini_app_user=self.user, task=first)
        # Тот же telegram_id в другом тенанте не должен влиять на этот тенант
        other_user = MiniAppUser.objects.create(tenant=self.other_tenant, telegram_id=7001, username='u2')
        MiniAppTaskStatistics.objects.create(mini_app_user=other_user, task=second)

        data = self.fetch().json()
        solved = {item['id']: item['is_solved'] for item in data['results']}
        self.assertEqual(solved, {first.id: True, second.id: False})
        self.assertEqual(data['completed_tasks_count'], 1)
