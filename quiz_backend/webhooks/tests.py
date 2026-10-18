import json

from django.test import TestCase, override_settings

from accounts.models import CustomUser
from donation.wallet_pay_service import WalletPayService
from tenants.middleware import clear_tenant_cache
from tenants.models import Tenant
from webhooks.models import Webhook


@override_settings(ALLOWED_HOSTS=['*'])
class WebhookSecurityTests(TestCase):
    def setUp(self):
        clear_tenant_cache()
        self.tenant_a = Tenant.objects.create(slug='wh-a', name='A', domain='wh-a.example.com', site_name='A')
        self.tenant_b = Tenant.objects.create(slug='wh-b', name='B', domain='wh-b.example.com', site_name='B')
        self.host_a = {'HTTP_HOST': 'wh-a.example.com'}

    @override_settings(TELEGRAM_WEBHOOK_SECRET='')
    def test_telegram_webhook_rejects_everything_without_configured_secret(self):
        response = self.client.post(
            '/api/webhooks/telegram/', data='{}', content_type='application/json',
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN='', **self.host_a,
        )
        self.assertEqual(response.status_code, 401)

    @override_settings(TELEGRAM_WEBHOOK_SECRET='s3cret')
    def test_telegram_webhook_rejects_wrong_secret(self):
        response = self.client.post(
            '/api/webhooks/telegram/', data='{}', content_type='application/json',
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN='wrong', **self.host_a,
        )
        self.assertEqual(response.status_code, 401)

    def test_regular_user_cannot_register_webhook(self):
        user = CustomUser.objects.create_user(username='regular', password='password123', tenant=self.tenant_a)
        self.client.force_login(user)
        response = self.client.post(
            '/api/webhooks/webhooks/',
            data=json.dumps({'url': 'https://attacker.example.com/hook', 'service_name': 'x'}),
            content_type='application/json', **self.host_a,
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Webhook.objects.filter(url='https://attacker.example.com/hook').exists())

    def test_staff_of_other_tenant_sees_no_webhooks(self):
        Webhook.objects.create(tenant=self.tenant_a, url='https://a.example.com/hook', service_name='a')
        staff_b = CustomUser.objects.create_user(
            username='staff_b', password='password123', tenant=self.tenant_b, is_staff=True
        )
        self.client.force_login(staff_b)
        response = self.client.get('/api/webhooks/webhooks/', **self.host_a)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        items = data.get('results', data) if isinstance(data, dict) else data
        self.assertEqual(items, [])

    def test_social_media_callback_without_tenant_is_rejected(self):
        response = self.client.post(
            '/api/webhooks/social-media-callback/',
            data=json.dumps({'task_id': 1, 'platform': 'pinterest', 'status': 'published'}),
            content_type='application/json', HTTP_HOST='unknown.example.com',
        )
        self.assertEqual(response.status_code, 404)

    @override_settings(SOCIAL_MEDIA_CALLBACK_SECRET='cb-secret')
    def test_social_media_callback_requires_configured_secret(self):
        response = self.client.post(
            '/api/webhooks/social-media-callback/',
            data=json.dumps({'task_id': 1, 'platform': 'pinterest', 'status': 'published'}),
            content_type='application/json', **self.host_a,
        )
        self.assertEqual(response.status_code, 403)

    @override_settings(WALLET_PAY_API_KEY='')
    def test_wallet_pay_signature_rejected_without_api_key(self):
        import hashlib
        import hmac
        body = '{"externalId": "1", "status": "PAID"}'
        forged = hmac.new(b'', body.encode(), hashlib.sha256).hexdigest()
        self.assertFalse(WalletPayService().verify_webhook(forged, body))
