import datetime

from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from accounts.models import MiniAppUser
from tasks.models import MiniAppTaskStatistics, Task
from tenants.middleware import clear_tenant_cache
from tenants.models import Tenant
from topics.models import Subtopic, Topic

URL = '/api/accounts/miniapp-users/top/'


@override_settings(ALLOWED_HOSTS=['*'])
class MiniAppTopUsersTests(TestCase):
    def setUp(self):
        clear_tenant_cache()
        self.tenant = Tenant.objects.create(
            slug='top-a', name='A', domain='top-a.example.com', mini_app_domain='mini.top-a.example.com', site_name='A'
        )
        self.python = Topic.objects.create(tenant=self.tenant, name='Python')
        self.go = Topic.objects.create(tenant=self.tenant, name='Go')
        subtopic = Subtopic.objects.create(topic=self.python, name='Basics')
        self.easy, self.hard, self.medium = [
            Task.objects.create(tenant=self.tenant, topic=self.python, subtopic=subtopic, difficulty=d, published=True)
            for d in ('easy', 'hard', 'medium')
        ]
        self.host = {'HTTP_HOST': 'mini.top-a.example.com'}
        self.next_id = 9000

    def make_user(self, public=True, **extra):
        self.next_id += 1
        user = MiniAppUser.objects.create(
            tenant=self.tenant, telegram_id=self.next_id, username=f'u{self.next_id}', is_profile_public=public, **extra
        )
        MiniAppTaskStatistics.objects.create(mini_app_user=user, task=self.easy, successful=True)
        MiniAppTaskStatistics.objects.create(mini_app_user=user, task=self.hard, successful=True)
        MiniAppTaskStatistics.objects.create(mini_app_user=user, task=self.medium, successful=False)
        return user

    def fetch(self, **params):
        return self.client.get(URL, params, **self.host)

    @staticmethod
    def app_queries(context):
        return [q for q in context.captured_queries if 'silk_' not in q['sql'] and 'SAVEPOINT' not in q['sql']]

    def test_rating_and_stats_values(self):
        user = self.make_user()
        row = {r['telegram_id']: r for r in self.fetch().json()}[user.telegram_id]
        self.assertEqual(row['rating'], 60)            # easy 10 + hard 50
        self.assertEqual(row['quizzes_completed'], 2)
        self.assertEqual(row['average_score'], 66.7)   # 2 из 3 попыток

    def test_language_filter_does_not_inflate_rating(self):
        user = self.make_user(programming_language=self.python)
        user.programming_languages.set([self.python, self.go])
        rows = self.fetch(language_pref='Python').json()
        self.assertEqual([r['telegram_id'] for r in rows], [user.telegram_id])
        self.assertEqual(rows[0]['rating'], 60)
        self.assertEqual(rows[0]['quizzes_completed'], 2)

    def test_private_profile_hides_birth_date(self):
        user = self.make_user(public=False, birth_date=datetime.date(1990, 5, 1))
        row = {r['telegram_id']: r for r in self.fetch().json()}[user.telegram_id]
        self.assertIsNone(row['birth_date'])
        self.assertIsNone(row['rating'])

    def test_query_count_does_not_grow_with_number_of_users(self):
        self.make_user()
        self.fetch()  # прогрев кэша тенантов
        with CaptureQueriesContext(connection) as small:
            self.fetch()
        for _ in range(5):
            self.make_user()
        with CaptureQueriesContext(connection) as large:
            response = self.fetch()
        self.assertEqual(len(response.json()), 6)
        self.assertEqual(len(self.app_queries(large)), len(self.app_queries(small)))
