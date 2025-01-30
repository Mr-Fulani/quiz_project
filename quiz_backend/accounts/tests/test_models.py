import pytest
from django.core.exceptions import ValidationError
from accounts.models import CustomUser, TelegramAdmin, DjangoAdmin, UserChannelSubscription
from platforms.models import TelegramChannel

@pytest.mark.django_db
class TestCustomUserModel:
    def test_create_user(self):
        user = CustomUser.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            language='ru'
        )
        assert user.username == 'testuser'
        assert user.email == 'test@example.com'
        assert user.language == 'ru'
        assert not user.is_staff
        assert not user.is_superuser
        assert user.is_active

    def test_create_superuser(self):
        admin = CustomUser.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        assert admin.is_staff
        assert admin.is_superuser
        assert admin.is_active

    def test_user_str(self):
        user = CustomUser.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        assert str(user) == 'testuser'

@pytest.mark.django_db
class TestTelegramAdminModel:
    def test_create_telegram_admin(self):
        admin = TelegramAdmin.objects.create(
            username='tgadmin',
            email='tg@example.com',
            password='tgpass123',
            telegram_id=123456789,
            is_staff=True
        )
        assert admin.telegram_id == 123456789
        assert admin.is_staff

    def test_telegram_admin_str(self):
        admin = TelegramAdmin.objects.create(
            username='tgadmin',
            email='tg@example.com',
            password='tgpass123',
            telegram_id=123456789
        )
        assert str(admin) == 'tgadmin (Telegram ID: 123456789)'

@pytest.mark.django_db
class TestDjangoAdminModel:
    def test_create_django_admin(self):
        admin = DjangoAdmin.objects.create(
            username='djadmin',
            email='dj@example.com',
            password='djpass123',
            is_staff=True,
            is_superuser=True
        )
        assert admin.is_staff
        assert admin.is_superuser

    def test_django_admin_str(self):
        admin = DjangoAdmin.objects.create(
            username='djadmin',
            email='dj@example.com',
            password='djpass123'
        )
        assert str(admin) == 'djadmin'

@pytest.mark.django_db
class TestUserChannelSubscriptionModel:
    def test_create_subscription(self, test_user):
        channel = TelegramChannel.objects.create(
            group_name='Test Channel',
            group_id=123456789,
            topic_id=1,
            language='ru',
            location_type='group'
        )
        subscription = UserChannelSubscription.objects.create(
            user=test_user,
            channel=channel,
            subscription_status='inactive'
        )
        assert subscription.user == test_user
        assert subscription.channel == channel
        assert subscription.subscription_status == 'inactive'

    def test_subscription_str(self, test_user):
        channel = TelegramChannel.objects.create(
            group_name='Test Channel',
            group_id=123456789,
            topic_id=1,
            language='ru',
            location_type='group'
        )
        subscription = UserChannelSubscription.objects.create(
            user=test_user,
            channel=channel
        )
        expected_str = f'Подписка {test_user.username} на {channel.group_name} ({channel.group_id}) (Неактивна)'
        assert str(subscription) == expected_str 