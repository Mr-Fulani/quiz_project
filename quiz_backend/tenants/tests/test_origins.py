"""Домены сайтов берутся из тенантов: доверие CORS/CSRF, ссылки, публичные данные тенанта."""
from django.http import HttpResponse
from django.test import Client, RequestFactory, TestCase, override_settings

from tenants.middleware import clear_tenant_cache
from tenants.models import Tenant
from tenants.origins import clear_tenant_hosts_cache, is_tenant_origin
from tenants.scoping import public_host, site_host, site_url_for


class TenantOriginsTest(TestCase):
    def setUp(self):
        clear_tenant_cache()
        clear_tenant_hosts_cache()
        self.tenant = Tenant.objects.create(
            slug='tenant-a', name='A', domain='a.example.com',
            mini_app_domain='mini.a.example.com', site_name='Site A',
        )
        Tenant.objects.create(slug='off', name='Off', domain='off.example.com', is_active=False)
        self.factory = RequestFactory()

    def test_trusted_origins_follow_tenants(self):
        self.assertTrue(is_tenant_origin('https://a.example.com'))
        self.assertTrue(is_tenant_origin('https://www.a.example.com'))
        self.assertTrue(is_tenant_origin('https://mini.a.example.com'))
        self.assertFalse(is_tenant_origin('http://a.example.com'))
        self.assertFalse(is_tenant_origin('https://off.example.com'))
        self.assertFalse(is_tenant_origin('https://evil.example.com'))
        self.assertFalse(is_tenant_origin(None))

    def test_new_domain_is_trusted_after_save(self):
        self.assertFalse(is_tenant_origin('https://new-site.org'))
        self.tenant.domain = 'new-site.org'
        self.tenant.save()
        self.assertTrue(is_tenant_origin('https://new-site.org'))
        self.assertFalse(is_tenant_origin('https://a.example.com'))

    @override_settings(CORS_ALLOW_ALL_ORIGINS=False, CORS_ALLOWED_ORIGINS=[])
    def test_cors_allows_tenant_origin_only(self):
        client = Client()
        ok = client.get('/health/', HTTP_HOST='a.example.com', HTTP_ORIGIN='https://mini.a.example.com')
        self.assertEqual(ok.headers.get('Access-Control-Allow-Origin'), 'https://mini.a.example.com')
        bad = client.get('/health/', HTTP_HOST='a.example.com', HTTP_ORIGIN='https://evil.example.com')
        self.assertIsNone(bad.headers.get('Access-Control-Allow-Origin'))

    def test_csrf_trusts_tenant_origin(self):
        from tenants.origins import TenantCsrfViewMiddleware
        middleware = TenantCsrfViewMiddleware(lambda request: HttpResponse())

        def origin_ok(origin):
            request = self.factory.post('/x/', HTTP_HOST='a.example.com', HTTP_ORIGIN=origin, secure=True)
            return middleware._origin_verified(request)

        self.assertTrue(origin_ok('https://mini.a.example.com'))
        self.assertFalse(origin_ok('https://evil.example.com'))

    def test_link_helpers(self):
        request = self.factory.get('/', HTTP_HOST='mini.a.example.com')
        request.tenant = self.tenant
        self.assertEqual(site_host(request), 'a.example.com')
        self.assertEqual(public_host(request), 'mini.a.example.com')
        self.assertEqual(site_url_for(self.tenant), 'https://a.example.com')
        with self.settings(PUBLIC_URL='https://fallback.org/', SITE_URL=''):
            self.assertEqual(site_url_for(None), 'https://fallback.org')

    def test_current_tenant_endpoint(self):
        response = Client().get('/api/tenant/', HTTP_HOST='mini.a.example.com')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['site_url'], 'https://a.example.com')
        self.assertEqual(response.json()['mini_app_url'], 'https://mini.a.example.com')
        self.assertNotIn('bot_token', response.json())
