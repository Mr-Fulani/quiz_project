import json
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import CustomUser
from blog.models import Message, MessageAttachment, message_attachment_upload_to
from tenants.middleware import clear_tenant_cache
from tenants.models import Tenant

MEDIA_DIR = tempfile.mkdtemp()


@override_settings(ALLOWED_HOSTS=['*'], MEDIA_ROOT=MEDIA_DIR, DEBUG=False)
class MessageAttachmentPrivacyTests(TestCase):
    def setUp(self):
        clear_tenant_cache()
        self.tenant = Tenant.objects.create(slug='att-a', name='A', domain='att-a.example.com', site_name='A')
        self.other_tenant = Tenant.objects.create(slug='att-b', name='B', domain='att-b.example.com', site_name='B')
        self.sender = CustomUser.objects.create_user(username='att_sender', password='p', tenant=self.tenant)
        self.recipient = CustomUser.objects.create_user(username='att_recipient', password='p', tenant=self.tenant)
        self.stranger = CustomUser.objects.create_user(username='att_stranger', password='p', tenant=self.tenant)
        message = Message.objects.create(
            tenant=self.tenant, sender=self.sender, recipient=self.recipient, content='hi'
        )
        self.attachment = MessageAttachment.objects.create(
            message=message,
            file=SimpleUploadedFile('паспорт "скан".pdf', b'%PDF-1.4 test', content_type='application/pdf'),
            filename='паспорт "скан".pdf',
        )
        self.host = {'HTTP_HOST': 'att-a.example.com'}

    def download(self, user):
        self.client.force_login(user)
        return self.client.get(reverse('blog:download_attachment', args=[self.attachment.id]), **self.host)

    def test_stored_name_is_random_not_original(self):
        self.assertNotIn('паспорт', self.attachment.file.name)
        self.assertTrue(self.attachment.file.name.startswith('message_attachments/'))
        self.assertTrue(message_attachment_upload_to(None, 'scan.PDF').endswith('.pdf'))

    def test_participant_gets_file_via_x_accel_redirect(self):
        response = self.download(self.recipient)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['X-Accel-Redirect'], f'/protected-media/{self.attachment.file.name}')
        self.assertIn('attachment', response['Content-Disposition'])
        # Кавычки и кириллица из имени файла не ломают заголовок
        self.assertNotIn('"скан"', response['Content-Disposition'])

    def test_stranger_is_denied(self):
        self.assertEqual(self.download(self.stranger).status_code, 403)

    def test_staff_of_same_tenant_allowed_other_tenant_denied(self):
        own_staff = CustomUser.objects.create_user(username='att_staff_a', password='p', tenant=self.tenant, is_staff=True)
        other_staff = CustomUser.objects.create_user(
            username='att_staff_b', password='p', tenant=self.other_tenant, is_staff=True
        )
        self.assertEqual(self.download(own_staff).status_code, 200)
        self.assertEqual(self.download(other_staff).status_code, 403)

    def test_conversation_json_uses_protected_url(self):
        self.client.force_login(self.recipient)
        response = self.client.get(
            reverse('blog:get_conversation', args=['att_sender']), **self.host
        )
        attachment_url = json.loads(response.content)['messages'][0]['attachments'][0]['url']
        self.assertEqual(attachment_url, self.attachment.get_download_url(inline=True))
        self.assertNotIn('/media/', attachment_url)
