from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase

from tasks.services.default_link_service import DefaultLinkService
from tasks.services.social_media_service import _active_credentials
from tenants.models import Tenant
from tenants.scoping import for_tenant_or_shared
from webhooks.models import DefaultLink, SocialMediaCredentials, Webhook
from webhooks.services import send_webhooks_for_bulk_tasks, send_webhooks_for_task


class TenantScopingOfIntegrationsTests(TestCase):
    """Фоновые интеграции не должны использовать вебхуки, ссылки и ключи чужого тенанта."""

    def setUp(self):
        self.tenant_a = Tenant.objects.create(slug='sc-a', name='A', domain='sc-a.example.com', site_name='A')
        self.tenant_b = Tenant.objects.create(slug='sc-b', name='B', domain='sc-b.example.com', site_name='B')
        Webhook.objects.create(tenant=self.tenant_a, url='https://a.example.com/hook')
        Webhook.objects.create(tenant=self.tenant_b, url='https://b.example.com/hook')
        Webhook.objects.create(tenant=None, url='https://shared.example.com/hook')

    def test_for_tenant_or_shared(self):
        urls = set(for_tenant_or_shared(Webhook.objects.all(), self.tenant_a).values_list('url', flat=True))
        self.assertEqual(urls, {'https://a.example.com/hook', 'https://shared.example.com/hook'})

    @patch('webhooks.services.create_full_webhook_data', return_value={'translations': []})
    @patch('webhooks.services.send_task_published_webhook', return_value=True)
    def test_task_webhooks_go_only_to_own_and_shared(self, send, _payload):
        send_webhooks_for_task(SimpleNamespace(id=1, tenant=self.tenant_a))
        sent_to = {call.args[0] for call in send.call_args_list}
        self.assertEqual(sent_to, {'https://a.example.com/hook', 'https://shared.example.com/hook'})

    @patch('webhooks.services.create_bulk_webhook_data', return_value={})
    @patch('webhooks.services.create_full_webhook_data', return_value={'translations': []})
    @patch('webhooks.services.send_task_published_webhook', return_value=True)
    def test_bulk_webhooks_are_split_by_tenant(self, send, _full, _bulk):
        task_a = SimpleNamespace(id=1, tenant=self.tenant_a, tenant_id=self.tenant_a.id)
        task_b = SimpleNamespace(id=2, tenant=self.tenant_b, tenant_id=self.tenant_b.id)
        send_webhooks_for_bulk_tasks([task_a, task_b])
        sent_to = [call.args[0] for call in send.call_args_list]
        # Каждый тенант — в свои вебхуки; общий получает две раздельные отправки
        self.assertEqual(sent_to.count('https://a.example.com/hook'), 1)
        self.assertEqual(sent_to.count('https://b.example.com/hook'), 1)
        self.assertEqual(sent_to.count('https://shared.example.com/hook'), 2)

    def test_default_link_of_other_tenant_is_not_used(self):
        DefaultLink.objects.create(tenant=self.tenant_b, language='ru', topic='Python', link='https://b.example.com/')
        self.assertIsNone(DefaultLinkService.get_default_link('ru', 'Python', tenant=self.tenant_a))
        self.assertEqual(
            DefaultLinkService.get_default_link('ru', 'Python', tenant=self.tenant_b), 'https://b.example.com/'
        )

    def test_social_credentials_of_other_tenant_are_not_used(self):
        SocialMediaCredentials.objects.create(tenant=self.tenant_b, platform='pinterest', access_token='b-token')
        self.assertIsNone(_active_credentials('pinterest', self.tenant_a))
        shared = SocialMediaCredentials.objects.create(tenant=None, platform='pinterest', access_token='shared')
        self.assertEqual(_active_credentials('pinterest', self.tenant_a), shared)
