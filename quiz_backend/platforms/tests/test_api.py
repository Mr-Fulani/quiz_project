import pytest
from django.urls import reverse
from platforms.models import Group
from topics.models import Topic

@pytest.mark.django_db
class TestTelegramChannelEndpoints:
    @pytest.fixture
    def test_topic(self):
        return Topic.objects.create(
            name='Test Topic',
            description='Test Description'
        )

    def test_channel_list(self, api_client, test_admin, test_topic):
        api_client.force_authenticate(user=test_admin)
        channel1 = Group.objects.create(
            group_name='Python Channel',
            group_id=123456789,
            topic_id=test_topic.id,
            language='ru',
            location_type='group'
        )
        channel2 = Group.objects.create(
            group_name='JavaScript Channel',
            group_id=987654321,
            topic_id=test_topic.id,
            language='en',
            location_type='channel'
        )

        url = reverse('platforms:telegram-channel-list')
        response = api_client.get(url)

        assert response.status_code == 200
        assert len(response.data['results']) == 2
        channels = {channel['group_name'] for channel in response.data['results']}
        assert channels == {'Python Channel', 'JavaScript Channel'}

    def test_channel_detail(self, api_client, test_admin, test_topic):
        api_client.force_authenticate(user=test_admin)
        channel = Group.objects.create(
            group_name='Python Channel',
            group_id=123456789,
            topic_id=test_topic.id,
            language='ru',
            location_type='group'
        )

        url = reverse('platforms:telegram-channel-detail', kwargs={'pk': channel.id})
        response = api_client.get(url)

        assert response.status_code == 200
        assert response.data['group_name'] == 'Python Channel'
        assert response.data['group_id'] == 123456789
        assert response.data['language'] == 'ru'

    def test_channel_create(self, api_client, test_admin, test_topic):
        api_client.force_authenticate(user=test_admin)
        url = reverse('platforms:telegram-channel-list')
        data = {
            'group_name': 'New Channel',
            'group_id': 123456789,
            'topic_id': test_topic.id,
            'language': 'ru',
            'location_type': 'group'
        }
        response = api_client.post(url, data)

        assert response.status_code == 201
        assert Group.objects.count() == 1
        channel = Group.objects.first()
        assert channel.group_name == 'New Channel'
        assert channel.group_id == 123456789

    def test_channel_update(self, api_client, test_admin, test_topic):
        api_client.force_authenticate(user=test_admin)
        channel = Group.objects.create(
            group_name='Python Channel',
            group_id=123456789,
            topic_id=test_topic.id,
            language='ru',
            location_type='group'
        )

        url = reverse('platforms:telegram-channel-detail', kwargs={'pk': channel.id})
        data = {
            'group_name': 'Updated Channel',
            'language': 'en'
        }
        response = api_client.patch(url, data)

        assert response.status_code == 200
        channel.refresh_from_db()
        assert channel.group_name == 'Updated Channel'
        assert channel.language == 'en'

    def test_channel_delete(self, api_client, test_admin, test_topic):
        api_client.force_authenticate(user=test_admin)
        channel = Group.objects.create(
            group_name='Python Channel',
            group_id=123456789,
            topic_id=test_topic.id,
            language='ru',
            location_type='group'
        )

        url = reverse('platforms:telegram-channel-detail', kwargs={'pk': channel.id})
        response = api_client.delete(url)

        assert response.status_code == 204
        assert not Group.objects.exists()

    def test_unauthorized_access(self, api_client):
        url = reverse('platforms:telegram-channel-list')
        response = api_client.get(url)
        assert response.status_code == 401

    def test_non_admin_access(self, api_client, test_user):
        api_client.force_authenticate(user=test_user)
        url = reverse('platforms:telegram-channel-list')
        response = api_client.get(url)
        assert response.status_code == 403
