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

    def test_matching_github_login_does_not_take_over_site_account(self):
        from social_auth.services import GitHubAuthService
        user = GitHubAuthService._get_or_create_user(
            {'id': 555, 'login': 'admin_victim', 'name': '', 'email': ''}, tenant=self.tenant
        )
        self.assertNotEqual(user.pk, self.victim.pk)
        self.assertFalse(user.is_staff)

    def test_matching_google_name_does_not_take_over_telegram_account(self):
        from social_auth.models import SocialAccount
        from social_auth.services import GoogleAuthService
        telegram_user = CustomUser.objects.create_user(
            username='tg_only', password='password123', tenant=self.tenant, first_name='Ivan', last_name='Petrov'
        )
        SocialAccount.objects.create(
            user=telegram_user, tenant=self.tenant, provider='telegram', provider_user_id='999', is_active=True
        )
        user = GoogleAuthService._get_or_create_user(
            {'id': 'g-1', 'email': 'attacker@example.com', 'first_name': 'Ivan', 'last_name': 'Petrov'},
            tenant=self.tenant,
        )
        self.assertNotEqual(user.pk, telegram_user.pk)
        telegram_user.refresh_from_db()
        self.assertFalse(telegram_user.email)

    def test_existing_telegram_id_still_logs_into_own_account(self):
        self.victim.telegram_id = 777001
        self.victim.save()
        user = TelegramAuthService._get_or_create_user({'id': 777001, 'username': 'whatever'}, tenant=self.tenant)
        self.assertEqual(user.pk, self.victim.pk)
