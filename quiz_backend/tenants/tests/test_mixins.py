from django.contrib import admin
from django.test import RequestFactory, TestCase

from accounts.models import CustomUser, UserChannelSubscription
from tasks.models import Task
from tenants.models import Tenant


class TenantAdminMixinTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.tenant_a = Tenant.objects.create(slug='mx-a', name='A', domain='mx-a.example.com', site_name='A')
        self.tenant_b = Tenant.objects.create(slug='mx-b', name='B', domain='mx-b.example.com', site_name='B')
        self.task_admin = admin.site._registry[Task]

    def request_for(self, user, request_tenant):
        request = self.factory.get('/admin/')
        request.user = user
        # request.tenant зависит от заголовков запроса — для staff он не должен иметь значения
        request.tenant = request_tenant
        return request

    def test_staff_without_tenant_cannot_borrow_tenant_from_request(self):
        staff = CustomUser.objects.create_user(username='no_tenant_staff', password='password123', is_staff=True)
        request = self.request_for(staff, self.tenant_a)
        self.assertIsNone(self.task_admin._get_current_tenant(request))
        self.assertFalse(self.task_admin.get_queryset(request).exists())

    def test_staff_uses_own_tenant_not_request_tenant(self):
        staff_b = CustomUser.objects.create_user(
            username='staff_b_mx', password='password123', tenant=self.tenant_b, is_staff=True
        )
        request = self.request_for(staff_b, self.tenant_a)
        self.assertEqual(self.task_admin._get_current_tenant(request), self.tenant_b)

    def test_channel_subscriptions_admin_is_tenant_filtered(self):
        subscription_admin = admin.site._registry[UserChannelSubscription]
        self.assertEqual(subscription_admin.tenant_lookup, 'channel__tenant')
        staff = CustomUser.objects.create_user(username='sub_staff', password='password123', is_staff=True)
        self.assertFalse(subscription_admin.get_queryset(self.request_for(staff, self.tenant_a)).exists())
