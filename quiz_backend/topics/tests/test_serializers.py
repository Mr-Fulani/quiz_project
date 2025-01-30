import pytest
from topics.models import Topic, Subtopic
from topics.serializers import TopicSerializer, SubtopicSerializer

@pytest.mark.django_db
class TestTopicSerializer:
    def test_topic_serialization(self):
        topic = Topic.objects.create(
            name='Python',
            description='Python programming'
        )
        serializer = TopicSerializer(topic)
        data = serializer.data

        assert data['name'] == 'Python'
        assert data['description'] == 'Python programming'
        assert 'id' in data

    def test_topic_deserialization(self):
        data = {
            'name': 'JavaScript',
            'description': 'JS programming'
        }
        serializer = TopicSerializer(data=data)
        assert serializer.is_valid()
        topic = serializer.save()

        assert topic.name == 'JavaScript'
        assert topic.description == 'JS programming'

@pytest.mark.django_db
class TestSubtopicSerializer:
    def test_subtopic_serialization(self, test_topic):
        subtopic = Subtopic.objects.create(
            name='Basics',
            topic=test_topic
        )
        serializer = SubtopicSerializer(subtopic)
        data = serializer.data

        assert data['name'] == 'Basics'
        assert data['topic'] == test_topic.id
        assert 'id' in data

    def test_subtopic_deserialization(self, test_topic):
        data = {
            'name': 'Advanced',
            'topic': test_topic.id
        }
        serializer = SubtopicSerializer(data=data)
        assert serializer.is_valid()
        subtopic = serializer.save()

        assert subtopic.name == 'Advanced'
        assert subtopic.topic == test_topic

    def test_subtopic_with_invalid_topic(self):
        data = {
            'name': 'Advanced',
            'topic': 999  # Несуществующий topic_id
        }
        serializer = SubtopicSerializer(data=data)
        assert not serializer.is_valid()
        assert 'topic' in serializer.errors

    @pytest.fixture
    def test_topic(self):
        return Topic.objects.create(
            name='Python',
            description='Python programming'
        )
