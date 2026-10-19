import importlib
from unittest.mock import patch

from django.apps import apps
from django.test import RequestFactory, TestCase, override_settings

from blog.context_processors import seo_context
from tasks.services.image_generation_service import get_tenant_logo_path
from tenants.models import Tenant

fill_migration = importlib.import_module('tenants.migrations.0004_fill_tenant_author_and_image_settings')


class TenantSettingsFieldsTests(TestCase):
    """Автор, контакты и стиль картинок берутся из полей тенанта, а не из сравнения slug."""

    def make_tenant(self, slug='ts-a', **fields):
        return Tenant.objects.create(slug=slug, name=slug, domain=f'{slug}.example.com', site_name=slug, **fields)

    def test_defaults_are_neutral(self):
        tenant = self.make_tenant()
        self.assertEqual(tenant.author_name, '')
        self.assertEqual(tenant.contact_phone, '')
        self.assertEqual(tenant.social_profile_urls, [])
        self.assertFalse(tenant.is_author_site)
        self.assertEqual(tenant.image_theme, Tenant.IMAGE_THEME_CODE)
        self.assertFalse(tenant.use_global_logo)

    def test_social_profile_urls_skip_blank_lines(self):
        tenant = self.make_tenant(social_profiles=' https://t.me/a \n\n https://youtube.com/@a\n')
        self.assertEqual(tenant.social_profile_urls, ['https://t.me/a', 'https://youtube.com/@a'])

    def test_data_migration_keeps_previous_values(self):
        quiz_code = self.make_tenant('quiz-code')
        iqro = self.make_tenant('iqro-forum')
        other = self.make_tenant('other')

        fill_migration.fill_values(apps, None)

        quiz_code.refresh_from_db()
        self.assertEqual(quiz_code.author_name, 'Anvar Sh.')
        self.assertEqual(quiz_code.contact_phone, '+90-552-582-1497')
        self.assertEqual(len(quiz_code.social_profile_urls), 3)
        self.assertTrue(quiz_code.is_author_site)
        self.assertTrue(quiz_code.use_global_logo)
        self.assertEqual(quiz_code.image_theme, Tenant.IMAGE_THEME_CODE)
        iqro.refresh_from_db()
        self.assertEqual(iqro.image_theme, Tenant.IMAGE_THEME_ISLAMIC)
        self.assertEqual(iqro.author_name, '')
        self.assertFalse(iqro.use_global_logo)
        other.refresh_from_db()
        self.assertEqual(other.author_name, '')
        self.assertEqual(other.image_theme, Tenant.IMAGE_THEME_CODE)

    def test_global_logo_flag_skips_tenant_logo(self):
        tenant = self.make_tenant(use_global_logo=True, logo='tenants/logos/a.png')
        with patch('tasks.services.image_generation_service.os.path.exists', return_value=True):
            self.assertIsNone(get_tenant_logo_path(tenant))
            tenant.use_global_logo = False
            self.assertIsNotNone(get_tenant_logo_path(tenant))


@override_settings(ALLOWED_HOSTS=['*'])
class SeoContextAuthorTests(TestCase):
    def context_for(self, tenant, path='/'):
        request = RequestFactory().get(path, HTTP_HOST=tenant.domain)
        request.tenant = tenant
        return seo_context(request)

    def test_author_phone_and_profiles_come_from_tenant(self):
        tenant = Tenant.objects.create(
            slug='ts-author', name='A', domain='ts-author.example.com', site_name='A',
            author_name='Jane Doe', contact_phone='+1-555-0100', social_profiles='https://t.me/jane',
        )
        context = self.context_for(tenant)

        self.assertEqual(context['meta_author'], 'Jane Doe')
        self.assertIn('"name": "Jane Doe"', context['website_json_ld'])
        self.assertIn('"telephone": "+1-555-0100"', context['organization_json_ld'])
        self.assertIn('https://t.me/jane', context['organization_json_ld'])

    def test_tenant_without_author_gets_generic_values(self):
        tenant = Tenant.objects.create(slug='ts-plain', name='P', domain='ts-plain.example.com', site_name='P')
        context = self.context_for(tenant)

        self.assertEqual(context['meta_author'], 'Developer')
        self.assertIn('"sameAs": []', context['organization_json_ld'])
        self.assertIn('"telephone": ""', context['organization_json_ld'])
