from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from tenants.middleware import TenantMiddleware, clear_tenant_cache
from tenants.models import Tenant


class TenantMiddlewareSpoofingTests(TestCase):
    def setUp(self):
        clear_tenant_cache()
        self.factory = RequestFactory()
        self.tenant_a = Tenant.objects.create(
            slug='tenant-a', name='A', domain='a.example.com',
            mini_app_domain='mini.a.example.com', site_name='A',
        )
        self.tenant_b = Tenant.objects.create(
            slug='tenant-b', name='B', domain='b.example.com',
            mini_app_domain='mini.b.example.com', site_name='B',
        )
        self.middleware = TenantMiddleware(lambda request: HttpResponse())

    def resolve(self, **extra):
        request = self.factory.get('/', **extra)
        self.middleware(request)
        return request.tenant

    def test_resolves_by_host(self):
        self.assertEqual(self.resolve(HTTP_HOST='a.example.com'), self.tenant_a)
        self.assertEqual(self.resolve(HTTP_HOST='www.b.example.com'), self.tenant_b)
        self.assertEqual(self.resolve(HTTP_HOST='mini.a.example.com'), self.tenant_a)

    def test_resolves_by_x_forwarded_host_set_by_nginx(self):
        tenant = self.resolve(HTTP_HOST='quiz_backend:8000', HTTP_X_FORWARDED_HOST='mini.b.example.com')
        self.assertEqual(tenant, self.tenant_b)

    def test_ignores_x_tenant_slug_header(self):
        tenant = self.resolve(HTTP_HOST='a.example.com', HTTP_X_TENANT_SLUG='tenant-b', HTTP_X_TENANT='tenant-b')
        self.assertEqual(tenant, self.tenant_a)

    def test_ignores_spoofable_proxy_headers(self):
        tenant = self.resolve(
            HTTP_HOST='a.example.com',
            HTTP_X_ORIGINAL_HOST='b.example.com',
            HTTP_X_REAL_HOST='b.example.com',
            HTTP_FORWARDED='host=b.example.com',
        )
        self.assertEqual(tenant, self.tenant_a)

    def test_unknown_host_does_not_fall_back_to_origin_or_referer(self):
        tenant = self.resolve(
            HTTP_HOST='unknown.example.com',
            HTTP_ORIGIN='https://b.example.com',
            HTTP_REFERER='https://b.example.com/page',
        )
        self.assertIsNone(tenant)

    def test_no_single_active_tenant_fallback(self):
        self.tenant_b.is_active = False
        self.tenant_b.save()
        clear_tenant_cache()
        self.assertIsNone(self.resolve(HTTP_HOST='unknown.example.com'))
