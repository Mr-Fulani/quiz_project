from django.contrib import admin
from django.contrib.auth.models import Permission
from django.test import RequestFactory, TestCase, override_settings

from accounts.models import CustomUser, DjangoAdmin
from tenants.middleware import clear_tenant_cache
from tenants.models import Tenant


@override_settings(ALLOWED_HOSTS=['*'])
class AdminPrivilegeEscalationTests(TestCase):
    def setUp(self):
        clear_tenant_cache()
        self.factory = RequestFactory()
        self.tenant = Tenant.objects.create(slug='adm-a', name='A', domain='adm-a.example.com', site_name='A')
        self.staff = CustomUser.objects.create_user(
            username='tenant_staff', password='password123', tenant=self.tenant, is_staff=True
        )
        self.staff.user_permissions.add(
            Permission.objects.get(codename='change_customuser'),
            Permission.objects.get(codename='view_djangoadmin'),
            Permission.objects.get(codename='change_djangoadmin'),
        )
        self.superuser = CustomUser.objects.create_superuser(
            username='root', password='password123', email='root@example.com'
        )
        self.user_admin = admin.site._registry[CustomUser]
        self.django_admin_admin = admin.site._registry[DjangoAdmin]

    def make_request(self, user):
        request = self.factory.get('/admin/', HTTP_HOST='adm-a.example.com')
        request.user = CustomUser.objects.get(pk=user.pk)
        request.tenant = self.tenant
        return request

    def test_staff_cannot_edit_permission_fields(self):
        request = self.make_request(self.staff)
        readonly = self.user_admin.get_readonly_fields(request, self.staff)
        for field in ('is_superuser', 'groups', 'user_permissions'):
            self.assertIn(field, readonly)

        form_class = self.user_admin.get_form(request, self.staff)
        for field in ('is_superuser', 'groups', 'user_permissions'):
            self.assertNotIn(field, form_class.base_fields)

    def test_superuser_can_still_edit_permission_fields(self):
        request = self.make_request(self.superuser)
        readonly = self.user_admin.get_readonly_fields(request, self.staff)
        for field in ('is_superuser', 'groups', 'user_permissions'):
            self.assertNotIn(field, readonly)

    def test_django_admin_section_is_superuser_only(self):
        staff_request = self.make_request(self.staff)
        self.assertFalse(self.django_admin_admin.has_module_permission(staff_request))
        self.assertFalse(self.django_admin_admin.has_view_permission(staff_request))
        self.assertFalse(self.django_admin_admin.has_change_permission(staff_request))

        super_request = self.make_request(self.superuser)
        self.assertTrue(self.django_admin_admin.has_module_permission(super_request))
        self.assertTrue(self.django_admin_admin.has_change_permission(super_request))

    def test_staff_cannot_run_make_superuser_action(self):
        # Действие make_superuser доступно только со страницы списка, а её staff открыть не может
        self.client.force_login(self.staff)
        target = DjangoAdmin.objects.get(username='tenant_staff')
        response = self.client.post(
            '/admin/accounts/djangoadmin/',
            {'action': 'make_superuser', '_selected_action': [target.pk]},
            HTTP_HOST='adm-a.example.com',
        )
        self.assertEqual(response.status_code, 403)
        self.staff.refresh_from_db()
        self.assertFalse(self.staff.is_superuser)
