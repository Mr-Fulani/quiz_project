from django.test import TestCase

from accounts.models import CustomUser, DjangoAdmin, MiniAppUser
from accounts.serializers import MiniAppUserCreateSerializer
from tenants.models import Tenant


class TenantSafeDjangoAdminLinkingTests(TestCase):
    def create_tenant(self, slug):
        return Tenant.objects.create(
            slug=slug,
            name=f"Tenant {slug}",
            domain=f"{slug}.example.com",
            mini_app_domain=f"mini-{slug}.example.com",
            site_name=f"Tenant {slug}",
        )

    def test_miniapp_create_does_not_autolink_global_django_admin_by_username_only(self):
        tenant = self.create_tenant("tenant-a")
        CustomUser.objects.create_user(
            username="global_admin",
            password="password123",
            tenant=None,
            is_staff=True,
        )
        django_admin = DjangoAdmin.objects.get(username="global_admin")

        serializer = MiniAppUserCreateSerializer(
            data={
                "telegram_id": 1001,
                "username": "global_admin",
                "first_name": "Mini",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        mini_app_user = serializer.save(tenant=tenant)

        self.assertIsNone(mini_app_user.django_admin)
        self.assertIsNone(mini_app_user.linked_custom_user)
        self.assertEqual(django_admin.username, "global_admin")

    def test_miniapp_create_links_django_admin_only_through_linked_staff_custom_user(self):
        tenant = self.create_tenant("tenant-b")
        staff_user = CustomUser.objects.create_user(
            username="tenant_staff",
            password="password123",
            tenant=tenant,
            telegram_id=2002,
            is_staff=True,
        )

        serializer = MiniAppUserCreateSerializer(
            data={
                "telegram_id": 2002,
                "username": "telegram_handle",
                "first_name": "Staff",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        mini_app_user = serializer.save(tenant=tenant)
        mini_app_user.refresh_from_db()

        self.assertEqual(mini_app_user.linked_custom_user, staff_user)
        self.assertIsNotNone(mini_app_user.django_admin)
        self.assertEqual(mini_app_user.django_admin.username, staff_user.username)

    def test_link_to_django_admin_requires_linked_staff_custom_user(self):
        tenant = self.create_tenant("tenant-c")
        mini_app_user = MiniAppUser.objects.create(
            tenant=tenant,
            telegram_id=3003,
            username="orphan_mini_user",
        )
        CustomUser.objects.create_user(
            username="orphan_mini_user",
            password="password123",
            tenant=None,
            is_staff=True,
        )
        django_admin = DjangoAdmin.objects.get(username="orphan_mini_user")

        with self.assertRaisesMessage(ValueError, "linked_custom_user"):
            mini_app_user.link_to_django_admin(django_admin)
