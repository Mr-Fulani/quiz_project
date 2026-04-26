from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomUser
from blog.models import GlobalChatBan, GlobalChatMessage
from tenants.models import Tenant


class GlobalChatTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(
            slug='test-chat',
            name='Test Chat',
            domain='test-chat.local',
            site_name='Test Chat Site'
        )
        self.user = CustomUser.objects.create_user(
            username='user_one',
            email='user_one@example.com',
            password='password123',
            tenant=self.tenant
        )
        self.other_user = CustomUser.objects.create_user(
            username='user_two',
            email='user_two@example.com',
            password='password123',
            tenant=self.tenant
        )
        self.admin_user = CustomUser.objects.create_user(
            username='admin_user',
            email='admin_user@example.com',
            password='password123',
            tenant=self.tenant,
            is_staff=True
        )
        self.tenant_header = {'HTTP_X_TENANT_SLUG': self.tenant.slug}

    def test_global_chat_send_message(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('blog:global_chat_send'),
            {'content': 'Привет @user_two'},
            **self.tenant_header
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(GlobalChatMessage.objects.count(), 1)
        payload = response.json()
        self.assertEqual(payload['status'], 'sent')
        self.assertIn('@user_two', payload['message']['content_html'])

    def test_global_chat_reply_message(self):
        original = GlobalChatMessage.objects.create(tenant=self.tenant, author=self.other_user, content='Оригинал')
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('blog:global_chat_send'),
            {'content': 'Ответ', 'reply_to_id': original.id},
            **self.tenant_header
        )
        self.assertEqual(response.status_code, 200)
        reply = GlobalChatMessage.objects.order_by('-id').first()
        self.assertEqual(reply.reply_to_id, original.id)
        payload = response.json()
        self.assertEqual(payload['status'], 'sent')
        self.assertIsNotNone(payload['message']['reply_to'])
        self.assertEqual(payload['message']['reply_to']['id'], original.id)

    def test_global_chat_messages_incremental_loading(self):
        GlobalChatMessage.objects.create(tenant=self.tenant, author=self.user, content='Первое')
        second = GlobalChatMessage.objects.create(tenant=self.tenant, author=self.other_user, content='Второе')
        self.client.force_login(self.user)

        # Первичная загрузка возвращает события и курсор since
        initial = self.client.get(reverse('blog:global_chat_messages'), **self.tenant_header)
        self.assertEqual(initial.status_code, 200)
        initial_payload = initial.json()
        self.assertIn('since', initial_payload)

        # Инкрементальная загрузка: изменим сообщение после курсора
        second.content = 'Второе (обновлено)'
        second.save(update_fields=['content', 'updated_at'])

        response = self.client.get(
            reverse('blog:global_chat_messages'),
            {'since': initial_payload['since']},
            **self.tenant_header
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('events', payload)
        message_events = [e for e in payload['events'] if e.get('type') == 'message']
        self.assertGreaterEqual(len(message_events), 1)
        self.assertEqual(message_events[-1]['message']['id'], second.id)

    def test_deleted_message_is_sent_as_event(self):
        message = GlobalChatMessage.objects.create(tenant=self.tenant, author=self.user, content='Удалю')
        self.client.force_login(self.admin_user)

        initial = self.client.get(reverse('blog:global_chat_messages'), **self.tenant_header)
        cursor = initial.json()['since']

        self.client.post(
            reverse('blog:global_chat_delete', kwargs={'message_id': message.id}),
            **self.tenant_header
        )

        response = self.client.get(
            reverse('blog:global_chat_messages'),
            {'since': cursor},
            **self.tenant_header
        )
        self.assertEqual(response.status_code, 200)
        events = response.json().get('events', [])
        deleted_events = [e for e in events if e.get('type') == 'deleted' and e.get('message_id') == message.id]
        self.assertEqual(len(deleted_events), 1)

    def test_banned_user_cannot_send(self):
        GlobalChatBan.objects.create(tenant=self.tenant, user=self.user, banned_by=self.admin_user, reason='Спам')
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('blog:global_chat_send'),
            {'content': 'Сообщение'},
            **self.tenant_header
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(GlobalChatMessage.objects.count(), 0)

    def test_admin_can_delete_message(self):
        message = GlobalChatMessage.objects.create(tenant=self.tenant, author=self.user, content='Удаляемое')
        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse('blog:global_chat_delete', kwargs={'message_id': message.id}),
            **self.tenant_header
        )
        self.assertEqual(response.status_code, 200)
        message.refresh_from_db()
        self.assertTrue(message.is_deleted)

    def test_non_admin_cannot_ban(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('blog:global_chat_ban', kwargs={'user_id': self.other_user.id}),
            {'reason': 'Тест'},
            **self.tenant_header
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(GlobalChatBan.objects.filter(user=self.other_user, tenant=self.tenant).exists())
