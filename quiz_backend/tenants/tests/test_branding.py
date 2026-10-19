from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import RequestFactory, TestCase, override_settings

from accounts.utils import send_password_reset_email
from blog.models import PlatformResource, TenantInfo
from donation.models import Donation
from donation.utils import send_donation_thank_you_email
from tenants.branding import email_branding
from tenants.models import Tenant


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', ALLOWED_HOSTS=['*'])
class EmailBrandingTests(TestCase):
    """Название, email поддержки и соцсети в письмах берутся из данных тенанта."""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            slug='br-a', name='Brand A', domain='br-a.example.com', site_name='Brand A Site',
            contact_email='help@br-a.example.com',
        )
        PlatformResource.objects.create(tenant=self.tenant, title_ru='Канал', title_en='Channel',
                                        url='https://t.me/brand_a', order=0)
        PlatformResource.objects.create(tenant=self.tenant, title_ru='Скрыт', title_en='Hidden',
                                        url='https://hidden.example.com', is_active=False)

    def test_branding_values(self):
        branding = email_branding(self.tenant, 'ru')
        self.assertEqual(branding['site_name'], 'Brand A Site')
        self.assertEqual(branding['support_email'], 'help@br-a.example.com')
        self.assertEqual(branding['social_links'], [{'title': 'Канал', 'url': 'https://t.me/brand_a'}])

    def test_support_email_falls_back_to_owner(self):
        self.tenant.contact_email = ''
        self.tenant.save()
        TenantInfo.objects.create(tenant=self.tenant, name_ru='A', name_en='A', title_ru='T', title_en='T',
                                  email='owner@br-a.example.com')
        self.assertEqual(email_branding(self.tenant)['support_email'], 'owner@br-a.example.com')

    def test_without_tenant_is_empty(self):
        self.assertEqual(email_branding(None), {'site_name': '', 'support_email': '', 'social_links': []})

    def test_donation_email_uses_tenant_data(self):
        donation = Donation.objects.create(
            tenant=self.tenant, name='Bob', email='bob@example.com', amount=Decimal('5'),
            currency='usd', status='completed',
        )

        self.assertTrue(send_donation_thank_you_email(donation))

        message = mail.outbox[0]
        self.assertIn('Brand A Site', message.subject)
        html = message.alternatives[0][0]
        for body in (message.body, html):
            self.assertIn('https://t.me/brand_a', body)
            self.assertIn('help@br-a.example.com', body)
            self.assertNotIn('hidden.example.com', body)
            self.assertNotIn('Fulani', body)

    def test_password_reset_email_uses_tenant_data(self):
        user = get_user_model().objects.create_user(username='bob', email='bob@example.com', password='x' * 12)
        request = RequestFactory().get('/', HTTP_HOST='br-a.example.com')
        request.tenant = self.tenant

        send_password_reset_email(request, user, 'uid', 'token')

        message = mail.outbox[0]
        self.assertIn('Brand A Site', message.subject)
        html = message.alternatives[0][0]
        self.assertIn('https://t.me/brand_a', html)
        self.assertIn('mailto:help@br-a.example.com', html)
        self.assertNotIn('Quiz Project', html)
        self.assertIn('Brand A Site', message.body)
