import pytest
from django.db import IntegrityError
from platforms.models import TelegramChannel
from topics.models import Topic

@pytest.mark.django_db
class TestTelegramChannelModel:
    @pytest.fixture
    def test_topic(self):
        return Topic.objects.create(
            name='Test Topic',
            description='Test Description'
        )

    def test_create_channel(self, test_topic):
        channel = TelegramChannel.objects.create(
            group_name='Python Channel',
            group_id=123456789,
            topic_id=test_topic.id,
            language='ru',
            location_type='group'
        )
        assert channel.group_name == 'Python Channel'
        assert channel.group_id == 123456789
        assert channel.topic_id == test_topic.id
        assert channel.language == 'ru'
        assert channel.location_type == 'group'

    def test_channel_str(self, test_topic):
        channel = TelegramChannel.objects.create(
            group_name='Python Channel',
            group_id=123456789,
            topic_id=test_topic.id,
            language='ru',
            location_type='group'
        )
        assert str(channel) == 'Python Channel (123456789)'

    def test_channel_topic_relationship(self, test_topic):
        channel = TelegramChannel.objects.create(
            group_name='Python Channel',
            group_id=123456789,
            topic_id=test_topic.id,
            language='ru',
            location_type='group'
        )
        assert channel.topic_id == test_topic.id
        assert TelegramChannel.objects.filter(topic_id=test_topic.id).exists()

    def test_unique_group_id(self, test_topic):
        TelegramChannel.objects.create(
            group_name='Python Channel',
            group_id=123456789,
            topic_id=test_topic.id,
            language='ru',
            location_type='group'
        )
        with pytest.raises(IntegrityError):
            TelegramChannel.objects.create(
                group_name='Another Channel',
                group_id=123456789,  # тот же group_id
                topic_id=test_topic.id,
                language='ru',
                location_type='group'
            )
