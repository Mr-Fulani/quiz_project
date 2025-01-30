import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from tasks.models import Task, TaskTranslation, TaskStatistics
from topics.models import Topic, Subtopic
from accounts.models import CustomUser

@pytest.fixture
def test_topic(db):
    return Topic.objects.create(
        name='Python',
        description='Python programming'
    )

@pytest.fixture
def test_subtopic(test_topic):
    return Subtopic.objects.create(
        name='Basics',
        topic=test_topic
    )

@pytest.mark.django_db
class TestTaskModel:
    def test_task_creation(self, test_topic, test_subtopic):
        task = Task.objects.create(
            topic=test_topic,
            subtopic=test_subtopic,
            difficulty='easy',
            published=True
        )
        assert task.pk is not None
        assert str(task) == f"Задача {task.id} (Легкий)"

    def test_task_publish(self, test_topic, test_subtopic):
        task = Task.objects.create(
            topic=test_topic,
            subtopic=test_subtopic,
            difficulty='easy',
            published=False
        )
        assert task.publish_date is None
        
        task.published = True
        task.save()
        assert task.publish_date is not None

    def test_invalid_publish_date(self, test_topic, test_subtopic):
        task = Task.objects.create(
            topic=test_topic,
            subtopic=test_subtopic,
            difficulty='easy'
        )
        task.publish_date = timezone.now() - timezone.timedelta(days=1)
        with pytest.raises(ValidationError):
            task.clean()

@pytest.mark.django_db
class TestTaskTranslationModel:
    def test_translation_creation(self, test_topic, test_subtopic):
        task = Task.objects.create(
            topic=test_topic,
            subtopic=test_subtopic,
            difficulty='easy'
        )
        translation = TaskTranslation.objects.create(
            task=task,
            language='ru',
            question='Тестовый вопрос',
            answers=['A', 'B', 'C'],
            correct_answer='A',
            explanation='Тестовое объяснение'
        )
        assert translation.pk is not None
        assert str(translation) == f"Перевод задачи {task.id} (ru)"

@pytest.mark.django_db
class TestTaskStatisticsModel:
    def test_statistics_creation(self, test_topic, test_subtopic, test_user):
        task = Task.objects.create(
            topic=test_topic,
            subtopic=test_subtopic,
            difficulty='easy'
        )
        stats = TaskStatistics.objects.create(
            user=test_user,
            task=task,
            attempts=1,
            successful=True,
            last_attempt_date=timezone.now()
        )
        assert stats.pk is not None
        assert str(stats) == f"Статистика: Задача {task.id}, Пользователь {test_user.id}" 