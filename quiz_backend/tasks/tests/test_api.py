import pytest
from django.urls import reverse
from tasks.models import Task, TaskTranslation
from topics.models import Topic, Subtopic

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

@pytest.fixture
def test_task(test_topic, test_subtopic):
    task = Task.objects.create(
        topic=test_topic,
        subtopic=test_subtopic,
        difficulty='easy',
        published=True
    )
    TaskTranslation.objects.create(
        task=task,
        language='ru',
        question='Тестовый вопрос',
        answers=['A', 'B', 'C'],
        correct_answer='A',
        explanation='Тестовое объяснение'
    )
    return task

@pytest.mark.django_db
class TestTaskEndpoints:
    def test_task_list(self, api_client, test_user, test_task):
        api_client.force_authenticate(user=test_user)
        url = reverse('tasks:task-list')
        response = api_client.get(url)
        assert response.status_code == 200
        assert len(response.data) == 1

    def test_task_detail(self, api_client, test_user, test_task):
        api_client.force_authenticate(user=test_user)
        url = reverse('tasks:task-detail', args=[test_task.id])
        response = api_client.get(url)
        assert response.status_code == 200
        assert response.data['id'] == test_task.id

    def test_task_create(self, api_client, test_admin, test_topic, test_subtopic):
        api_client.force_authenticate(user=test_admin)
        url = reverse('tasks:task-create')
        data = {
            'topic_id': test_topic.id,
            'subtopic_id': test_subtopic.id,
            'difficulty': 'easy',
            'published': False,
            'translations': [{
                'language': 'ru',
                'question': 'Новый вопрос',
                'answers': ['X', 'Y', 'Z'],
                'correct_answer': 'X',
                'explanation': 'Тестовое объяснение'
            }]
        }
        response = api_client.post(url, data, format='json')
        print("Response content:", response.content)
        print("Response status:", response.status_code)
        print("Response data:", getattr(response, 'data', None))
        assert response.status_code == 201

    def test_task_submit(self, api_client, test_user, test_task):
        api_client.force_authenticate(user=test_user)
        url = reverse('tasks:task-submit', args=[test_task.id])
        data = {
            'answer': 'A',
            'time_spent': 30
        }
        response = api_client.post(url, data)
        assert response.status_code == 200

    def test_task_skip(self, api_client, test_user, test_task):
        api_client.force_authenticate(user=test_user)
        url = reverse('tasks:task-skip', args=[test_task.id])
        response = api_client.post(url)
        assert response.status_code == 200

    def test_next_task(self, api_client, test_user, test_task):
        api_client.force_authenticate(user=test_user)
        url = reverse('tasks:next-task')
        response = api_client.get(url)
        assert response.status_code == 200
