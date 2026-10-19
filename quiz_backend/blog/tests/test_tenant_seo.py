from django.core.cache import cache
from django.test import TestCase, override_settings

from blog.models import Category, Post
from tenants.models import Tenant


@override_settings(ALLOWED_HOSTS=['*'])
class TenantRobotsAndSitemapTests(TestCase):
    def setUp(self):
        cache.clear()
        self.tenant_a = Tenant.objects.create(slug='seo-a', name='A', domain='seo-a.example.com', site_name='A')
        self.tenant_b = Tenant.objects.create(slug='seo-b', name='B', domain='seo-b.example.com', site_name='B')
        for tenant, slug in ((self.tenant_a, 'post-of-a'), (self.tenant_b, 'post-of-b')):
            category = Category.objects.create(tenant=tenant, name=f'Cat {slug}', slug=f'cat-{slug}')
            Post.objects.create(tenant=tenant, title=slug, slug=slug, content='<p>x</p>',
                                category=category, published=True)

    def test_robots_points_to_own_domain_and_blocks_prefixed_service_pages(self):
        content = self.client.get('/robots.txt', HTTP_HOST='seo-a.example.com').content.decode()
        self.assertIn('Sitemap: https://seo-a.example.com/sitemap.xml', content)
        self.assertIn('Disallow: /en/swagger/', content)
        self.assertIn('Disallow: /ru/inbox/', content)

    def test_sitemap_lists_only_own_tenant_on_own_domain(self):
        content = self.client.get('/sitemap.xml', HTTP_HOST='seo-a.example.com').content.decode()
        self.assertIn('https://seo-a.example.com/', content)
        self.assertIn('post-of-a', content)
        self.assertNotIn('post-of-b', content)
        self.assertNotIn('seo-b.example.com', content)


@override_settings(ALLOWED_HOSTS=['*'])
class NoindexServicePagesTests(TestCase):
    def setUp(self):
        cache.clear()
        Tenant.objects.create(slug='seo-c', name='C', domain='seo-c.example.com', site_name='C')

    def test_password_reset_is_noindex(self):
        response = self.client.get('/en/accounts/password_reset/', HTTP_HOST='seo-c.example.com')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<meta name="robots" content="noindex, follow">', html=False)

    def test_regular_page_stays_indexable(self):
        response = self.client.get('/en/about/', HTTP_HOST='seo-c.example.com')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<meta name="robots" content="index, follow">', html=False)
