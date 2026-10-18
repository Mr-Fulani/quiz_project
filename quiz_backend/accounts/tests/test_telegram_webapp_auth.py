import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

from django.test import TestCase, override_settings

from accounts.api.mini_app_analytics import check_admin_access
from accounts.models import CustomUser, MiniAppUser
from accounts.telegram_webapp_auth import InitDataError, validate_init_data
from tenants.middleware import clear_tenant_cache
from tenants.models import Tenant

BOT_TOKEN_A = '111111:tenant-a-token'
BOT_TOKEN_B = '222222:tenant-b-token'


def make_init_data(bot_token, user, auth_date=None):
    """Строит initData, подписанный так же, как это делает Telegram."""
    fields = {
        'auth_date': str(auth_date if auth_date is not None else int(time.time())),
        'query_id': 'AAHdF6IQAAAAAN0XohDhrOrc',
        'user': json.dumps(user, separators=(',', ':')),
    }
    data_check_string = '\n'.join(f'{key}={value}' for key, value in sorted(fields.items()))
    secret_key = hmac.new(b'WebAppData', bot_token.encode(), hashlib.sha256).digest()
    fields['hash'] = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


class ValidateInitDataTests(TestCase):
    def test_valid_signature_returns_user(self):
        init_data = make_init_data(BOT_TOKEN_A, {'id': 42, 'first_name': 'Ann'})
        self.assertEqual(validate_init_data(init_data, BOT_TOKEN_A)['id'], 42)

    def test_wrong_bot_token_is_rejected(self):
        init_data = make_init_data(BOT_TOKEN_B, {'id': 42})
        with self.assertRaises(InitDataError):
            validate_init_data(init_data, BOT_TOKEN_A)

    def test_tampered_user_is_rejected(self):
        init_data = make_init_data(BOT_TOKEN_A, {'id': 42})
        forged = init_data.replace('%3A42', '%3A43')
        self.assertNotEqual(forged, init_data)
        with self.assertRaises(InitDataError):
            validate_init_data(forged, BOT_TOKEN_A)

    def test_unsigned_init_data_is_rejected(self):
        # То, что раньше принимала «ручная валидация»: user без hash
        with self.assertRaises(InitDataError):
            validate_init_data('user=%7B%22id%22%3A42%7D', BOT_TOKEN_A)

    def test_expired_init_data_is_rejected(self):
        init_data = make_init_data(BOT_TOKEN_A, {'id': 42}, auth_date=int(time.time()) - 3 * 24 * 3600)
        with self.assertRaises(InitDataError):
            validate_init_data(init_data, BOT_TOKEN_A, max_age_seconds=24 * 3600)


@override_settings(ALLOWED_HOSTS=['*'])
class MiniAppEndpointAuthTests(TestCase):
    def setUp(self):
        clear_tenant_cache()
        self.tenant = Tenant.objects.create(
            slug='tenant-a', name='A', domain='a.example.com',
            mini_app_domain='mini.a.example.com', site_name='A', bot_token=BOT_TOKEN_A,
        )
        self.other_tenant = Tenant.objects.create(
            slug='tenant-b', name='B', domain='b.example.com',
            mini_app_domain='mini.b.example.com', site_name='B', bot_token=BOT_TOKEN_B,
        )
        self.alice = MiniAppUser.objects.create(tenant=self.tenant, telegram_id=1001, username='alice')
        self.bob = MiniAppUser.objects.create(tenant=self.tenant, telegram_id=2002, username='bob')
        self.host = {'HTTP_HOST': 'mini.a.example.com'}

    def auth_headers(self, telegram_id, bot_token=BOT_TOKEN_A):
        init_data = make_init_data(bot_token, {'id': telegram_id, 'first_name': 'User'})
        return {**self.host, 'HTTP_X_TELEGRAM_INIT_DATA': init_data}

    def post_json(self, url, data, **headers):
        return self.client.post(url, data=json.dumps(data), content_type='application/json', **headers)

    def test_verify_endpoint_returns_verified_user(self):
        response = self.client.post('/api/accounts/miniapp-users/auth/verify/', **self.auth_headers(1001))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['user']['id'], 1001)

    def test_verify_endpoint_rejects_other_tenants_bot_signature(self):
        response = self.client.post(
            '/api/accounts/miniapp-users/auth/verify/', **self.auth_headers(1001, bot_token=BOT_TOKEN_B)
        )
        self.assertIn(response.status_code, (401, 403))

    def test_write_without_init_data_is_rejected(self):
        before = MiniAppUser.objects.get(pk=self.alice.pk).last_seen
        response = self.post_json(
            '/api/accounts/miniapp-users/update-last-seen/', {'telegram_id': 1001}, **self.host
        )
        self.assertIn(response.status_code, (401, 403))
        self.assertEqual(MiniAppUser.objects.get(pk=self.alice.pk).last_seen, before)

    def test_cannot_act_as_another_user(self):
        response = self.post_json(
            '/api/accounts/miniapp-users/update-last-seen/', {'telegram_id': 2002}, **self.auth_headers(1001)
        )
        self.assertIn(response.status_code, (401, 403))

    def test_own_write_with_valid_init_data_succeeds(self):
        response = self.post_json(
            '/api/accounts/miniapp-users/update-last-seen/', {'telegram_id': 1001}, **self.auth_headers(1001)
        )
        self.assertEqual(response.status_code, 200)

    def test_cannot_delete_another_users_profile(self):
        response = self.client.delete('/api/accounts/miniapp-users/2002/', **self.auth_headers(1001))
        self.assertIn(response.status_code, (401, 403))
        self.assertTrue(MiniAppUser.objects.filter(pk=self.bob.pk).exists())

    def test_cannot_delete_another_users_avatar(self):
        response = self.client.delete('/api/accounts/miniapp-users/2002/avatars/1/', **self.auth_headers(1001))
        self.assertIn(response.status_code, (401, 403))

    def test_cannot_update_another_users_profile(self):
        response = self.client.patch(
            '/api/accounts/miniapp-users/update/2002/', data=json.dumps({'first_name': 'Hacked'}),
            content_type='application/json', **self.auth_headers(1001),
        )
        self.assertIn(response.status_code, (401, 403))
        self.assertNotEqual(MiniAppUser.objects.get(pk=self.bob.pk).first_name, 'Hacked')

    def test_task_answer_requires_init_data(self):
        response = self.post_json('/api/tasks/1/submit-mini-app/', {'telegram_id': 1001, 'answer': 'x'}, **self.host)
        self.assertIn(response.status_code, (401, 403))

    def test_comment_cannot_be_posted_as_another_user(self):
        response = self.post_json(
            '/api/tasks/translations/1/comments/',
            {'author_telegram_id': 2002, 'text': 'spam'},
            **self.auth_headers(1001),
        )
        self.assertIn(response.status_code, (401, 403))

    def test_feedback_requires_init_data(self):
        response = self.post_json('/api/submit/', {'user_id': 1001, 'message': 'hello'}, **self.host)
        self.assertIn(response.status_code, (401, 403))

    def test_analytics_requires_init_data(self):
        response = self.client.get(
            '/api/accounts/mini-app-analytics/overview/', {'telegram_id': 1001}, **self.host
        )
        self.assertIn(response.status_code, (401, 403))

    def test_admin_check_is_scoped_to_tenant(self):
        MiniAppUser.objects.create(tenant=self.other_tenant, telegram_id=3003, username='carol')
        self.assertFalse(check_admin_access(3003, self.tenant))
        self.assertFalse(check_admin_access(1001, None))

    def test_profile_by_telegram_does_not_link_site_account_by_username(self):
        site_user = CustomUser.objects.create_user(username='victim', password='password123', tenant=self.tenant)
        self.post_json(
            '/api/accounts/profile/by-telegram/', {'telegram_id': 5005, 'username': 'victim'},
            **self.auth_headers(5005),
        )
        site_user.refresh_from_db()
        self.assertIsNone(site_user.telegram_id)
