import pytest
from rest_framework.test import APIClient
from accounts.models import CustomUser
from topics.models import Topic, Subtopic
from tasks.models import Task, TaskTranslation

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def test_user(db):
    return CustomUser.objects.create_user(
        username='testuser',
        password='testpass123',
        email='test@example.com',
        language='ru'
    )

@pytest.fixture
def test_admin(db):
    return CustomUser.objects.create_superuser(
        username='admin',
        password='adminpass123',
        email='admin@example.com'
    )

@pytest.fixture
def test_topic(db):
    return Topic.objects.create(
        name='Test Topic',
        description='Test Description'
    )

@pytest.fixture
def test_subtopic(db, test_topic):
    return Subtopic.objects.create(
        name='Test Subtopic',
        topic=test_topic
    )

@pytest.fixture
def test_task(db, test_topic, test_subtopic):
    task = Task.objects.create(
        topic=test_topic,
        subtopic=test_subtopic,
        difficulty='easy',
        published=True
    )
    TaskTranslation.objects.create(
        task=task,
        language='ru',
        question='Test Question',
        answers=['A', 'B', 'C'],
        correct_answer='A'
    )
    return task 