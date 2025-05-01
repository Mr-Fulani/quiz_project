import pytest
from accounts.serializers import (
    UserSerializer,
    LoginSerializer,
    RegisterSerializer,
    ProfileSerializer,
    SubscriptionSerializer,
    AdminSerializer
)
from accounts.models import CustomUser, TelegramAdmin, UserChannelSubscription
from platforms.models import Group

@pytest.mark.django_db
class TestUserSerializer:
    def test_user_serialization(self, test_user):
        serializer = UserSerializer(test_user)
        data = serializer.data
        assert data['username'] == test_user.username
        assert data['email'] == test_user.email
        assert data['language'] == test_user.language
        assert 'subscription_status' in data

@pytest.mark.django_db
class TestLoginSerializer:
    def test_valid_login(self, test_user):
        data = {
            'username': 'testuser',
            'password': 'testpass123'
        }
        serializer = LoginSerializer(data=data)
        assert serializer.is_valid()
        assert 'user' in serializer.validated_data
        assert serializer.validated_data['user'] == test_user

    def test_invalid_login(self):
        data = {
            'username': 'wronguser',
            'password': 'wrongpass'
        }
        serializer = LoginSerializer(data=data)
        assert not serializer.is_valid()
        assert 'non_field_errors' in serializer.errors

@pytest.mark.django_db
class TestRegisterSerializer:
    def test_valid_registration(self):
        data = {
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'newpass123',
            'password_confirm': 'newpass123',
            'language': 'ru'
        }
        serializer = RegisterSerializer(data=data)
        assert serializer.is_valid()
        user = serializer.save()
        assert user.username == 'newuser'
        assert user.email == 'new@example.com'
        assert user.check_password('newpass123')

    def test_password_mismatch(self):
        data = {
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'pass123',
            'password_confirm': 'pass456',
            'language': 'ru'
        }
        serializer = RegisterSerializer(data=data)
        assert not serializer.is_valid()
        assert 'non_field_errors' in serializer.errors

@pytest.mark.django_db
class TestProfileSerializer:
    def test_profile_serialization(self, test_user):
        serializer = ProfileSerializer(test_user)
        data = serializer.data
        assert data['username'] == test_user.username
        assert data['email'] == test_user.email
        assert data['language'] == test_user.language
        assert 'subscription_status' in data
        assert 'created_at' in data

    def test_profile_update(self, test_user):
        data = {
            'language': 'en',
            'first_name': 'Test',
            'last_name': 'User'
        }
        serializer = ProfileSerializer(test_user, data=data, partial=True)
        assert serializer.is_valid()
        updated_user = serializer.save()
        assert updated_user.language == 'en'
        assert updated_user.first_name == 'Test'
        assert updated_user.last_name == 'User'

@pytest.mark.django_db
class TestSubscriptionSerializer:
    def test_subscription_serialization(self, test_user):
        channel = Group.objects.create(
            group_name='Test Channel',
            group_id=123456789,
            topic_id=1,
            language='ru',
            location_type='group'
        )
        subscription = UserChannelSubscription.objects.create(
            user=test_user,
            channel=channel,
            subscription_status='active'
        )
        serializer = SubscriptionSerializer(subscription)
        data = serializer.data
        assert data['channel'] == channel.group_id
        assert data['channel_name'] == channel.group_name
        assert data['subscription_status'] == 'active'
        assert 'subscribed_at' in data

@pytest.mark.django_db
class TestAdminSerializer:
    def test_telegram_admin_serialization(self):
        admin = TelegramAdmin.objects.create(
            username='tgadmin',
            email='tg@example.com',
            password='tgpass123',
            telegram_id=123456789
        )
        serializer = AdminSerializer(admin)
        data = serializer.data
        assert data['username'] == 'tgadmin'
        assert data['email'] == 'tg@example.com'
        assert data['admin_type'] == 'telegram'
        assert data['telegram_id'] == 123456789 