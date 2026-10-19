import uuid

from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from accounts.models import CustomUser
from tasks.models import Task, TaskTranslation
from tenants.models import Tenant
from topics.models import Subtopic, Topic


@override_settings(ALLOWED_HOSTS=['*'])
class TaskAdminListTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(slug='tl-a', name='A', domain='tl-a.example.com', site_name='A')
        self.topic = Topic.objects.create(name='Python', tenant=self.tenant)
        self.subtopic = Subtopic.objects.create(name='Basics', topic=self.topic)
        self.admin_user = CustomUser.objects.create_superuser(
            username='tl_admin', email='tl@example.com', password='password123'
        )
        self.client.force_login(self.admin_user)
        self.url = reverse('admin:tasks_task_changelist')

    def make_task(self, question):
        task = Task.objects.create(
            tenant=self.tenant, topic=self.topic, subtopic=self.subtopic,
            difficulty='easy', translation_group_id=uuid.uuid4(),
        )
        TaskTranslation.objects.create(
            task=task, language='en', question=question,
            answers=['a', 'b'], correct_answer='a',
        )
        return task

    @staticmethod
    def app_queries(context):
        return [q for q in context.captured_queries
                if 'silk_' not in q['sql'] and 'SAVEPOINT' not in q['sql'] and not q['sql'].startswith('EXPLAIN')]

    def get(self, **params):
        return self.client.get(self.url, params, HTTP_HOST='tl-a.example.com')

    def test_list_shows_question_text(self):
        self.make_task('What does len([1, 2, 3]) return?')
        response = self.get()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'What does len([1, 2, 3]) return?')

    def test_search_by_question_text(self):
        wanted = self.make_task('How do generators work?')
        self.make_task('What is a decorator?')
        response = self.get(q='generators')
        self.assertEqual(list(response.context['cl'].result_list), [wanted])

    def test_translation_columns_do_not_query_per_row(self):
        self.make_task('Question 1')
        self.get()  # прогрев кэшей тенанта/сессии
        with CaptureQueriesContext(connection) as few:
            self.get()
        for i in range(2, 6):
            self.make_task(f'Question {i}')
        with CaptureQueriesContext(connection) as many:
            self.get()
        self.assertEqual(len(self.app_queries(many)), len(self.app_queries(few)))
