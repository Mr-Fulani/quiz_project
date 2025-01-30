import pytest
from topics.models import Topic, Subtopic

@pytest.mark.django_db
class TestTopicModel:
    def test_create_topic(self):
        topic = Topic.objects.create(
            name='Python',
            description='Python programming language'
        )
        assert topic.name == 'Python'
        assert topic.description == 'Python programming language'
        assert str(topic) == 'Python'

    def test_topic_with_subtopics(self):
        topic = Topic.objects.create(
            name='Python',
            description='Python programming language'
        )
        Subtopic.objects.create(name='Basics', topic=topic)
        Subtopic.objects.create(name='Advanced', topic=topic)

        assert topic.subtopics.count() == 2
        assert topic.subtopics.filter(name='Basics').exists()
        assert topic.subtopics.filter(name='Advanced').exists()

@pytest.mark.django_db
class TestSubtopicModel:
    def test_create_subtopic(self):
        topic = Topic.objects.create(
            name='Python',
            description='Python programming language'
        )
        subtopic = Subtopic.objects.create(
            name='Basics',
            topic=topic
        )
        assert subtopic.name == 'Basics'
        assert subtopic.topic == topic
        assert str(subtopic) == 'Python - Basics'

    def test_subtopic_ordering(self):
        topic = Topic.objects.create(
            name='Python',
            description='Python programming'
        )
        # Создаем подтемы в обратном порядке
        Subtopic.objects.create(name='Advanced', topic=topic)
        Subtopic.objects.create(name='Basics', topic=topic)
        
        # Получаем отсортированные подтемы
        subtopics = list(Subtopic.objects.order_by('name'))
        
        # Проверяем, что они в правильном порядке
        assert len(subtopics) == 2
        assert subtopics[0].name == 'Advanced'  # 'Advanced' идет первым по алфавиту
        assert subtopics[1].name == 'Basics'    # 'Basics' идет вторым

    def test_subtopic_cascade_delete(self):
        topic = Topic.objects.create(
            name='Python',
            description='Python programming'
        )
        Subtopic.objects.create(name='Basics', topic=topic)
        Subtopic.objects.create(name='Advanced', topic=topic)
        
        assert Subtopic.objects.count() == 2
        topic.delete()
        assert Subtopic.objects.count() == 0  # Проверяем, что подтемы удалились вместе с темой
