import pytest
from tasks.serializers import (
    TaskSerializer,
    TaskTranslationSerializer,
    TaskStatisticsSerializer,
    TaskSubmitSerializer
)
from tasks.models import Task, TaskTranslation, TaskStatistics

@pytest.mark.django_db
class TestTaskSerializer:
    def test_valid_task_serialization(self, test_task):
        serializer = TaskSerializer(test_task)
        data = serializer.data
        assert data['id'] == test_task.id
        assert data['difficulty'] == test_task.difficulty
        assert 'translations' in data

    def test_task_creation(self, test_topic, test_subtopic):
        data = {
            'topic_id': test_topic.id,
            'subtopic_id': test_subtopic.id,
            'difficulty': 'easy',
            'translations': [{
                'language': 'ru',
                'question': 'Новый вопрос',
                'answers': ['X', 'Y', 'Z'],
                'correct_answer': 'X'
            }]
        }
        serializer = TaskSerializer(data=data)
        assert serializer.is_valid()
        task = serializer.save()
        assert task.topic == test_topic
        assert task.subtopic == test_subtopic

    def test_invalid_task_data(self):
        data = {
            'difficulty': 'invalid_level'  # Неправильное значение
        }
        serializer = TaskSerializer(data=data)
        assert not serializer.is_valid()
        assert 'difficulty' in serializer.errors

@pytest.mark.django_db
class TestTaskTranslationSerializer:
    def test_translation_serialization(self, test_task):
        translation = test_task.translations.first()
        serializer = TaskTranslationSerializer(translation)
        data = serializer.data
        assert data['language'] == translation.language
        assert data['question'] == translation.question
        assert data['answers'] == translation.answers

    def test_translation_creation(self, test_task):
        data = {
            'task': test_task.id,
            'language': 'en',
            'question': 'Test question',
            'answers': ['A', 'B', 'C'],
            'correct_answer': 'A',
            'explanation': 'Test explanation'
        }
        serializer = TaskTranslationSerializer(data=data)
        assert serializer.is_valid()
        translation = serializer.save(task=test_task)
        assert translation.language == 'en'

@pytest.mark.django_db
class TestTaskSubmitSerializer:
    def test_valid_submit_data(self):
        data = {
            'answer': 'A',
            'time_spent': 30
        }
        serializer = TaskSubmitSerializer(data=data)
        assert serializer.is_valid()

    def test_invalid_submit_data(self):
        data = {
            'time_spent': 'invalid'  # Должно быть числом
        }
        serializer = TaskSubmitSerializer(data=data)
        assert not serializer.is_valid()
        assert 'time_spent' in serializer.errors 