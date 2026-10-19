from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from accounts.models import TelegramUser
from tenants.models import Tenant
from topics.models import Topic


class AssignTenantToLegacyRowsTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(slug='legacy-a', name='A', domain='legacy-a.example.com', site_name='A')
        self.other = Tenant.objects.create(slug='legacy-b', name='B', domain='legacy-b.example.com', site_name='B')
        Topic.objects.create(name='Legacy topic', tenant=None)
        Topic.objects.create(name='Other topic', tenant=self.other)
        TelegramUser.objects.create(telegram_id=1, tenant=None)

    def run_command(self, *args):
        out = StringIO()
        call_command('assign_tenant_to_legacy_rows', '--slug', 'legacy-a', *args, stdout=out)
        return out.getvalue()

    def test_dry_run_changes_nothing(self):
        output = self.run_command()
        self.assertIn('topics.Topic: 1', output)
        self.assertTrue(Topic.objects.filter(tenant__isnull=True).exists())

    def test_apply_assigns_only_null_rows(self):
        self.run_command('--apply')
        self.assertFalse(Topic.objects.filter(tenant__isnull=True).exists())
        self.assertEqual(Topic.objects.get(name='Other topic').tenant, self.other)
        self.assertEqual(TelegramUser.objects.get(telegram_id=1).tenant, self.tenant)

    def test_models_filter(self):
        self.run_command('--apply', '--models', 'topics.Topic')
        self.assertFalse(Topic.objects.filter(tenant__isnull=True).exists())
        self.assertTrue(TelegramUser.objects.filter(tenant__isnull=True).exists())
