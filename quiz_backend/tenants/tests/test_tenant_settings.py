import importlib
import shutil
import tempfile
from unittest.mock import patch

from django.apps import apps
from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import translation

from blog.context_processors import personal_info, seo_context
from blog.models import PlatformResource, TenantInfo
from tasks.services.image_generation_service import get_tenant_logo_path
from tenants.models import Tenant

tenant_migration = importlib.import_module('tenants.migrations.0004_fill_tenant_image_settings')
profile_migration = importlib.import_module('blog.migrations.0036_move_builtin_owner_profile_to_db')


def make_tenant(slug='ts-a', **fields):
    return Tenant.objects.create(slug=slug, name=slug, domain=f'{slug}.example.com', site_name=slug, **fields)


def make_owner(tenant, **fields):
    values = dict(name_ru='Иван', name_en='Ivan', title_ru='Дизайнер', title_en='Designer', email='ivan@example.com')
    values.update(fields)
    return TenantInfo.objects.create(tenant=tenant, **values)


class TenantImageSettingsTests(TestCase):
    """Стиль и логотип картинок берутся из полей тенанта, а не из сравнения slug."""

    def test_defaults(self):
        tenant = make_tenant()
        self.assertEqual(tenant.image_theme, Tenant.IMAGE_THEME_CODE)
        self.assertFalse(tenant.use_global_logo)

    def test_data_migration_keeps_previous_values(self):
        quiz_code, iqro, other = make_tenant('quiz-code'), make_tenant('iqro-forum'), make_tenant('other')

        tenant_migration.fill_values(apps, None)

        for tenant in (quiz_code, iqro, other):
            tenant.refresh_from_db()
        self.assertTrue(quiz_code.use_global_logo)
        self.assertEqual(quiz_code.image_theme, Tenant.IMAGE_THEME_CODE)
        self.assertEqual(iqro.image_theme, Tenant.IMAGE_THEME_ISLAMIC)
        self.assertFalse(iqro.use_global_logo)
        self.assertEqual(other.image_theme, Tenant.IMAGE_THEME_CODE)
        self.assertFalse(other.use_global_logo)

    def test_global_logo_flag_skips_tenant_logo(self):
        tenant = make_tenant(use_global_logo=True, logo='tenants/logos/a.png')
        with patch('tasks.services.image_generation_service.os.path.exists', return_value=True):
            self.assertIsNone(get_tenant_logo_path(tenant))
            tenant.use_global_logo = False
            self.assertIsNotNone(get_tenant_logo_path(tenant))


class BuiltinProfileMigrationTests(TestCase):
    """Встроенный профиль из кода переезжает в «Данные владельца» и «Ресурсы платформы»."""

    def setUp(self):
        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=media)
        override.enable()
        self.addCleanup(override.disable)

    def test_creates_owner_and_resources(self):
        tenant = make_tenant('quiz-code')

        profile_migration.move_profile(apps, None)

        info = TenantInfo.objects.get(tenant=tenant)
        self.assertEqual(info.name_en, 'Anvar Sh.')
        self.assertEqual(info.phone, '+90 (552) 582-1497')
        self.assertEqual(len(info.bio_ru.split('\n\n')), 4)
        self.assertTrue(info.home_text_en.startswith('Welcome to'))
        self.assertTrue(info.avatar.name.startswith('avatars/'))
        resources = PlatformResource.objects.filter(tenant=tenant).order_by('order')
        self.assertEqual([r.title_en for r in resources][:2], ['YouTube', 'Telegram'])
        self.assertTrue(all(r.icon_image for r in resources))

    def test_keeps_existing_owner_and_resources(self):
        tenant = make_tenant('quiz-code')
        make_owner(tenant)
        PlatformResource.objects.create(tenant=tenant, title_ru='X', title_en='X', url='https://x.example.com')

        profile_migration.move_profile(apps, None)

        self.assertEqual(TenantInfo.objects.get(tenant=tenant).name_en, 'Ivan')
        self.assertEqual(PlatformResource.objects.filter(tenant=tenant).count(), 1)

    def test_other_tenants_untouched(self):
        tenant = make_tenant('other')
        profile_migration.move_profile(apps, None)
        self.assertFalse(TenantInfo.objects.filter(tenant=tenant).exists())


@override_settings(ALLOWED_HOSTS=['*'])
class OwnerInfoInContextTests(TestCase):
    """Сайдбар и SEO берут автора, телефон и соцсети из «Данных владельца»."""

    def setUp(self):
        cache.clear()

    def request_for(self, tenant, path='/'):
        request = RequestFactory().get(path, HTTP_HOST=tenant.domain)
        request.tenant = tenant
        request.LANGUAGE_CODE = 'en'
        return request

    def test_seo_uses_owner(self):
        tenant = make_tenant('ts-owner')
        make_owner(tenant, phone='+1-555-0100', telegram='https://t.me/ivan', whatsapp='https://wa.me/1555')

        with translation.override('en'):
            context = seo_context(self.request_for(tenant))

        self.assertEqual(context['meta_author'], 'Ivan')
        self.assertIn('"name": "Ivan"', context['website_json_ld'])
        self.assertIn('"telephone": "+1-555-0100"', context['organization_json_ld'])
        self.assertIn('https://t.me/ivan', context['organization_json_ld'])
        self.assertNotIn('wa.me', context['organization_json_ld'])

    def test_resume_title_uses_owner_name(self):
        tenant = make_tenant('ts-resume')
        make_owner(tenant)

        with translation.override('en'):
            context = seo_context(self.request_for(tenant, reverse('blog:resume')))

        self.assertEqual(context['meta_title'], 'Ivan - Designer: resume and portfolio')

    def test_seo_without_owner_uses_site_name(self):
        tenant = make_tenant('ts-plain')

        with translation.override('en'):
            context = seo_context(self.request_for(tenant))

        self.assertEqual(context['meta_author'], 'ts-plain')
        self.assertIn('"sameAs": []', context['organization_json_ld'])
        self.assertIn('"telephone": ""', context['organization_json_ld'])

    def test_sidebar_texts_split_into_paragraphs(self):
        tenant = make_tenant('ts-side')
        make_owner(tenant, bio_en='First.\n\nSecond.', home_text_en='Home one.\n\nHome two.')

        data = personal_info(self.request_for(tenant))['personal_info']

        self.assertEqual(data['name'], 'Ivan')
        self.assertEqual(data['about_text'], ['First.', 'Second.'])
        self.assertEqual(data['home_text'], ['Home one.', 'Home two.'])

    def test_home_text_falls_back_to_bio(self):
        tenant = make_tenant('ts-bio')
        make_owner(tenant, bio_en='Only bio.')

        data = personal_info(self.request_for(tenant))['personal_info']

        self.assertEqual(data['home_text'], ['Only bio.'])
