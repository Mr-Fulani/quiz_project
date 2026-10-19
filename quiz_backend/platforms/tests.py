from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings

from accounts.models import CustomUser, TelegramUser
from platforms.admin import TelegramPostForm
from platforms.models import TelegramGroup
from platforms.services import send_post_to_bot_subscribers
from tenants.models import Tenant
from topics.models import Topic


@override_settings(ALLOWED_HOSTS=['*'])
class TelegramBroadcastTenantTests(TestCase):
    def setUp(self):
        self.tenant_a = Tenant.objects.create(slug='pl-a', name='A', domain='pl-a.example.com', site_name='A')
        self.tenant_b = Tenant.objects.create(slug='pl-b', name='B', domain='pl-b.example.com', site_name='B')
        topic_a = Topic.objects.create(tenant=self.tenant_a, name='Python')
        topic_b = Topic.objects.create(tenant=self.tenant_b, name='Go')
        self.channel_a = TelegramGroup.objects.create(
            tenant=self.tenant_a, group_name='A', group_id=-1001, topic_id=topic_a, language='ru'
        )
        self.channel_b = TelegramGroup.objects.create(
            tenant=self.tenant_b, group_name='B', group_id=-1002, topic_id=topic_b, language='ru'
        )
        self.staff_a = CustomUser.objects.create_user(
            username='pl_staff_a', password='password123', tenant=self.tenant_a, is_staff=True
        )
        self.staff_a.user_permissions.add(Permission.objects.get(codename='change_telegramgroup'))

    def test_form_without_queryset_offers_no_channels(self):
        self.assertFalse(TelegramPostForm().fields['channels'].queryset.exists())

    def test_staff_cannot_post_to_other_tenant_channel(self):
        self.client.force_login(self.staff_a)
        with patch('platforms.admin.send_telegram_post_sync', return_value=True) as send:
            response = self.client.post(
                '/admin/platforms/telegramgroup/send-post/',
                {'channels': [self.channel_b.id], 'text': 'spam'},
                HTTP_HOST='pl-a.example.com',
            )
        self.assertEqual(response.status_code, 200)  # форма невалидна: канала нет среди вариантов
        send.assert_not_called()

    def test_staff_without_change_permission_is_denied(self):
        viewer = CustomUser.objects.create_user(
            username='pl_viewer', password='password123', tenant=self.tenant_a, is_staff=True
        )
        self.client.force_login(viewer)
        response = self.client.get('/admin/platforms/telegramgroup/send-post/', HTTP_HOST='pl-a.example.com')
        self.assertEqual(response.status_code, 403)

    def test_subscriber_broadcast_requires_tenant_and_is_scoped(self):
        TelegramUser.objects.create(tenant=self.tenant_a, telegram_id=111)
        TelegramUser.objects.create(tenant=self.tenant_b, telegram_id=222)
        self.assertEqual(send_post_to_bot_subscribers(text='hi', tenant=None), 0)

        sent_to = []

        async def fake_send(user_id, **kwargs):
            sent_to.append(user_id)
            return True

        with patch('platforms.services.send_post_to_user_with_files', side_effect=fake_send):
            sent = send_post_to_bot_subscribers(text='hi', tenant=self.tenant_a)
        self.assertEqual(sent_to, [111])
        self.assertEqual(sent, 1)
