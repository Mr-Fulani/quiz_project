from django.test import TestCase

from accounts.models import CustomUser
from social_auth.services import TelegramAuthService
from tenants.models import Tenant


class TelegramLoginUsernameTakeoverTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(slug='sa-a', name='A', domain='sa-a.example.com', site_name='A')
        self.victim = CustomUser.objects.create_user(
            username='admin_victim', password='password123', tenant=self.tenant, is_staff=True
        )

    def test_matching_telegram_username_does_not_take_over_site_account(self):
        user = TelegramAuthService._get_or_create_user(
            {'id': 777000, 'username': 'admin_victim', 'first_name': ''}, tenant=self.tenant
        )
        self.assertNotEqual(user.pk, self.victim.pk)
        self.victim.refresh_from_db()
        self.assertIsNone(self.victim.telegram_id)
        self.assertFalse(user.is_staff)

    def test_existing_telegram_id_still_logs_into_own_account(self):
        self.victim.telegram_id = 777001
        self.victim.save()
        user = TelegramAuthService._get_or_create_user({'id': 777001, 'username': 'whatever'}, tenant=self.tenant)
        self.assertEqual(user.pk, self.victim.pk)
