from django.conf import settings
from django.test import TestCase, override_settings


@override_settings(ALLOWED_HOSTS=['*'])
class DefaultApiPermissionTests(TestCase):
    def test_default_permission_is_authenticated_or_read_only(self):
        self.assertEqual(
            settings.REST_FRAMEWORK['DEFAULT_PERMISSION_CLASSES'],
            ['rest_framework.permissions.IsAuthenticatedOrReadOnly'],
        )

    def test_view_without_explicit_permissions_rejects_anonymous_writes(self):
        # ProfileDeactivateView не задаёт permission_classes и раньше был открыт анонимам
        response = self.client.post('/api/accounts/profile/deactivate/')
        self.assertIn(response.status_code, (401, 403))
