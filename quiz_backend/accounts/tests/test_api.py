import pytest
from rest_framework.test import APIClient
from django.urls import reverse
from accounts.models import CustomUser, TelegramAdmin, DjangoAdmin, UserChannelSubscription
from platforms.models import Group


@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def test_user():
    return CustomUser.objects.create_user(
        username='testuser',
        password='testpass123',
        email='test@example.com',
        language='ru'
    )

@pytest.fixture
def test_admin():
    return CustomUser.objects.create_superuser(
        username='admin',
        password='adminpass123',
        email='admin@example.com'
    )

@pytest.fixture
def test_telegram_admin():
    return TelegramAdmin.objects.create(
        username='tgadmin',
        password='tgpass123',
        email='tg@example.com',
        telegram_id=123456789
    )

@pytest.fixture
def test_channel():
    return Group.objects.create(
        group_name='Test Channel',
        group_id=987654321,
        topic_id=1,
        language='ru',
        location_type='group'
    )

@pytest.mark.django_db
class TestAuthEndpoints:
    def test_register(self, api_client):
        url = reverse('accounts:register')
        data = {
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'newpass123',
            'password_confirm': 'newpass123',
            'language': 'ru'
        }
        response = api_client.post(url, data)
        assert response.status_code == 201
        assert CustomUser.objects.filter(username='newuser').exists()

    def test_login(self, api_client, test_user):
        url = reverse('accounts:login')
        data = {
            'username': 'testuser',
            'password': 'testpass123'
        }
        response = api_client.post(url, data)
        assert response.status_code == 200
        assert response.data['username'] == test_user.username

    def test_logout(self, api_client, test_user):
        api_client.force_authenticate(user=test_user)
        url = reverse('accounts:logout')
        response = api_client.post(url)
        assert response.status_code == 200

@pytest.mark.django_db
class TestProfileEndpoints:
    def test_profile_get(self, api_client, test_user):
        api_client.force_authenticate(user=test_user)
        url = reverse('accounts:profile')
        response = api_client.get(url)
        assert response.status_code == 200
        assert response.data['username'] == test_user.username
        assert response.data['email'] == test_user.email
        assert response.data['language'] == test_user.language

    def test_profile_update(self, api_client, test_user):
        api_client.force_authenticate(user=test_user)
        url = reverse('accounts:profile-update')
        data = {'language': 'en'}
        response = api_client.patch(url, data)
        assert response.status_code == 200
        assert response.data['language'] == 'en'

    def test_profile_deactivate(self, api_client, test_user):
        api_client.force_authenticate(user=test_user)
        url = reverse('accounts:profile-deactivate')
        response = api_client.post(url)
        assert response.status_code == 200
        test_user.refresh_from_db()
        assert not test_user.is_active

@pytest.mark.django_db
class TestSubscriptionEndpoints:
    @pytest.fixture
    def test_channel(self, db):
        return Group.objects.create(
            group_name='Test Channel',
            group_id=123456789,
            topic_id=1,
            language='ru',
            location_type='group'
        )

    def test_subscription_list(self, api_client, test_user, test_channel):
        api_client.force_authenticate(user=test_user)
        subscription = UserChannelSubscription.objects.create(
            user=test_user,
            channel=test_channel
        )
        url = reverse('accounts:subscription-list')
        response = api_client.get(url)
        assert response.status_code == 200
        assert len(response.data) == 1
        assert 'channel' in response.data[0]
        assert 'subscription_status' in response.data[0]

    def test_subscription_detail(self, api_client, test_user, test_channel):
        api_client.force_authenticate(user=test_user)
        subscription = UserChannelSubscription.objects.create(
            user=test_user,
            channel=test_channel
        )
        url = reverse('accounts:subscription-detail', kwargs={'pk': subscription.id})
        response = api_client.get(url)
        assert response.status_code == 200
        assert 'channel' in response.data
        assert 'subscription_status' in response.data
        assert response.data['channel'] == test_channel.group_id
        assert response.data['channel_name'] == test_channel.group_name

@pytest.mark.django_db
class TestAdminEndpoints:
    def test_admin_list(self, api_client, test_admin):
        api_client.force_authenticate(user=test_admin)
        url = reverse('accounts:admin-list')
        response = api_client.get(url)
        assert response.status_code == 200

    def test_telegram_admin_list(self, api_client, test_admin):
        api_client.force_authenticate(user=test_admin)
        url = reverse('accounts:telegram-admin-list')
        response = api_client.get(url)
        assert response.status_code == 200

    def test_django_admin_list(self, api_client, test_admin):
        api_client.force_authenticate(user=test_admin)
        url = reverse('accounts:django-admin-list')
        response = api_client.get(url)
        assert response.status_code == 200

@pytest.mark.django_db
class TestStatsEndpoints:
    def test_user_stats(self, api_client, test_user, test_channel):
        api_client.force_authenticate(user=test_user)
        UserChannelSubscription.objects.create(user=test_user, channel=test_channel)
        url = reverse('accounts:user-stats')
        response = api_client.get(url)
        assert response.status_code == 200
        assert 'subscriptions' in response.data
        assert response.data['subscriptions'] == 1 