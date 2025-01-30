import pytest
from platforms.models import TelegramChannel
from platforms.serializers import TelegramChannelSerializer
from topics.models import Topic

@pytest.mark.django_db
class TestTelegramChannelSerializer:
    @pytest.fixture
    def test_topic(self):
        return Topic.objects.create(
            name='Test Topic',
            description='Test Description'
        )

    def test_serialization(self, test_topic):
        channel = TelegramChannel.objects.create(
            group_name='Python Channel',
            group_id=123456789,
            topic_id=test_topic.id,
            language='ru',
            location_type='group'
        )
        serializer = TelegramChannelSerializer(channel)
        data = serializer.data

        assert data['group_name'] == 'Python Channel'
        assert data['group_id'] == 123456789
        assert data['topic_id'] == test_topic.id
        assert data['language'] == 'ru'
        assert data['location_type'] == 'group'

    def test_deserialization_valid_data(self, test_topic):
        data = {
            'group_name': 'New Channel',
            'group_id': 987654321,
            'topic_id': test_topic.id,
            'language': 'ru',
            'location_type': 'group'
        }
        serializer = TelegramChannelSerializer(data=data)
        assert serializer.is_valid()
        channel = serializer.save()
        assert channel.group_name == 'New Channel'
        assert channel.group_id == 987654321

    def test_invalid_location_type(self, test_topic):
        data = {
            'group_name': 'New Channel',
            'group_id': 987654321,
            'topic_id': test_topic.id,
            'language': 'ru',
            'location_type': 'invalid'
        }
        serializer = TelegramChannelSerializer(data=data)
        assert not serializer.is_valid()
        assert 'location_type' in serializer.errors

    def test_missing_required_fields(self):
        data = {}
        serializer = TelegramChannelSerializer(data=data)
        assert not serializer.is_valid()
        assert set(serializer.errors.keys()) == {
            'group_name', 'group_id', 'topic_id', 'language'
        }  # location_type не обязательное поле

    def test_partial_update(self, test_topic):
        channel = TelegramChannel.objects.create(
            group_name='Python Channel',
            group_id=123456789,
            topic_id=test_topic.id,
            language='ru',
            location_type='group'
        )
        data = {'group_name': 'Updated Channel'}
        serializer = TelegramChannelSerializer(
            channel, 
            data=data, 
            partial=True
        )
        assert serializer.is_valid()
        updated_channel = serializer.save()
        assert updated_channel.group_name == 'Updated Channel'
        assert updated_channel.group_id == 123456789  # остальные поля не изменились
