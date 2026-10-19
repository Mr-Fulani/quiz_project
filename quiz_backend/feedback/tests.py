import tempfile
from io import BytesIO
from unittest.mock import MagicMock

from django.contrib import admin
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from PIL import Image

from accounts.models import CustomUser
from feedback.models import FeedbackImage, FeedbackMessage
from tenants.models import Tenant

MEDIA_DIR = tempfile.mkdtemp()


class FeedbackAdminSaveFormsetTests(TestCase):
    def test_formset_is_saved_once(self):
        """Повторный formset.save() создавал вторую копию прикреплённой к ответу картинки."""
        model_admin = admin.site._registry[FeedbackMessage]
        formset = MagicMock()
        formset.save.return_value = []
        request = RequestFactory().post('/admin/')
        request.user = MagicMock()

        model_admin.save_formset(request, form=MagicMock(), formset=formset, change=True)

        committed_saves = [c for c in formset.save.call_args_list if c.kwargs.get('commit', True)]
        self.assertEqual(len(committed_saves), 1)


def png_file(name='shot.png'):
    buffer = BytesIO()
    Image.new('RGB', (2, 2)).save(buffer, format='PNG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/png')


@override_settings(ALLOWED_HOSTS=['*'], MEDIA_ROOT=MEDIA_DIR, DEBUG=False)
class ProtectedFeedbackImageTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(slug='fb-a', name='A', domain='fb-a.example.com', site_name='A')
        self.other_tenant = Tenant.objects.create(slug='fb-b', name='B', domain='fb-b.example.com', site_name='B')
        feedback = FeedbackMessage.objects.create(tenant=self.tenant, user_id=1, message='help')
        self.image = FeedbackImage.objects.create(feedback=feedback, image=png_file())
        self.url = self.image.get_protected_url()

    def get_as(self, user):
        if user:
            self.client.force_login(user)
        return self.client.get(self.url, HTTP_HOST='fb-a.example.com')

    def test_url_is_not_public_media_path(self):
        self.assertNotIn('/media/', self.url)

    def test_anonymous_and_regular_users_denied(self):
        self.assertEqual(self.get_as(None).status_code, 403)
        regular = CustomUser.objects.create_user(username='fb_user', password='p', tenant=self.tenant)
        self.assertEqual(self.get_as(regular).status_code, 403)

    def test_staff_of_own_tenant_gets_x_accel_redirect(self):
        staff = CustomUser.objects.create_user(username='fb_staff', password='p', tenant=self.tenant, is_staff=True)
        response = self.get_as(staff)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['X-Accel-Redirect'], f'/protected-media/{self.image.image.name}')

    def test_staff_of_other_tenant_denied(self):
        staff_b = CustomUser.objects.create_user(
            username='fb_staff_b', password='p', tenant=self.other_tenant, is_staff=True
        )
        self.assertEqual(self.get_as(staff_b).status_code, 403)
