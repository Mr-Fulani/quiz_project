from django.core.cache import cache
from django.db import connection
from django.test import RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from blog.context_processors import dynamic_seo_context, personal_info
from blog.models import Category, Post, TenantInfo
from tenants.models import Tenant


@override_settings(ALLOWED_HOSTS=['*'])
class PersonalInfoCacheTests(TestCase):
    def setUp(self):
        cache.clear()
        self.tenant = Tenant.objects.create(slug='cp-a', name='A', domain='cp-a.example.com', site_name='A Site')
        self.factory = RequestFactory()

    def make_request(self, path='/en/'):
        request = self.factory.get(path, HTTP_HOST='cp-a.example.com')
        request.tenant = self.tenant
        request.LANGUAGE_CODE = 'en'
        return request

    def test_second_page_view_uses_cache(self):
        personal_info(self.make_request())
        with CaptureQueriesContext(connection) as queries:
            result = personal_info(self.make_request('/en/blog/'))
        self.assertEqual(len(queries.captured_queries), 0)
        self.assertIn('top_users', result['personal_info'])

    def test_tenant_info_change_resets_cache(self):
        personal_info(self.make_request())
        TenantInfo.objects.create(tenant=self.tenant, name_en='New Owner')
        result = personal_info(self.make_request())
        self.assertEqual(result['personal_info']['name'], 'New Owner')


@override_settings(ALLOWED_HOSTS=['*'])
class DynamicSeoContextTests(TestCase):
    def test_post_seo_is_built(self):
        """Раньше NameError (connection.close без импорта) молча обнулял SEO постов."""
        tenant = Tenant.objects.create(slug='cp-b', name='B', domain='cp-b.example.com', site_name='B Site')
        category = Category.objects.create(tenant=tenant, name='News', slug='cp-news')
        Post.objects.create(tenant=tenant, title='Hello', slug='cp-hello', content='<p>Body</p>',
                            category=category, published=True)
        request = RequestFactory().get('/en/post/cp-hello/', HTTP_HOST='cp-b.example.com')
        request.tenant = tenant
        seo = dynamic_seo_context(request)['dynamic_seo']
        self.assertEqual(seo.get('meta_title'), 'Hello | B Site')
        self.assertIn('article_json_ld', seo)
