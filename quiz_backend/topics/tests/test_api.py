import pytest
from django.urls import reverse
from topics.models import Topic, Subtopic

@pytest.mark.django_db
class TestTopicEndpoints:
    def test_topic_list(self, api_client, test_user):
        api_client.force_authenticate(user=test_user)
        Topic.objects.create(name='Python', description='Python programming')
        Topic.objects.create(name='JavaScript', description='JS programming')
        
        url = reverse('topics:topic-list')
        response = api_client.get(url)
        
        assert response.status_code == 200
        assert len(response.data) == 2
        topics = {topic['name'] for topic in response.data}
        assert topics == {'Python', 'JavaScript'}

    def test_topic_detail(self, api_client, test_user):
        api_client.force_authenticate(user=test_user)
        topic = Topic.objects.create(
            name='Python',
            description='Python programming'
        )
        
        url = reverse('topics:topic-detail', kwargs={'pk': topic.id})
        response = api_client.get(url)
        
        assert response.status_code == 200
        assert response.data['name'] == 'Python'
        assert response.data['description'] == 'Python programming'

    def test_topic_create(self, api_client, test_admin):
        api_client.force_authenticate(user=test_admin)
        url = reverse('topics:topic-create')
        data = {
            'name': 'New Topic',
            'description': 'New Description'
        }
        response = api_client.post(url, data)
        
        assert response.status_code == 201
        assert Topic.objects.count() == 1
        assert Topic.objects.first().name == 'New Topic'

@pytest.mark.django_db
class TestSubtopicEndpoints:
    def test_subtopic_list(self, api_client, test_user, test_topic):
        api_client.force_authenticate(user=test_user)
        Subtopic.objects.create(name='Basics', topic=test_topic)
        Subtopic.objects.create(name='Advanced', topic=test_topic)
        
        url = reverse('topics:topic-subtopics', kwargs={'topic_id': test_topic.id})
        response = api_client.get(url)
        
        assert response.status_code == 200
        assert len(response.data) == 2
        subtopics = {subtopic['name'] for subtopic in response.data}
        assert subtopics == {'Basics', 'Advanced'}

    def test_subtopic_detail(self, api_client, test_user):
        api_client.force_authenticate(user=test_user)
        topic = Topic.objects.create(name='Python', description='Python programming')
        subtopic = Subtopic.objects.create(name='Basics', topic=topic)
        
        url = reverse('topics:subtopic-detail', kwargs={'pk': subtopic.id})
        response = api_client.get(url)
        
        assert response.status_code == 200
        assert response.data['name'] == 'Basics'
        assert response.data['topic'] == topic.id

    def test_subtopic_create(self, api_client, test_admin, test_topic):
        api_client.force_authenticate(user=test_admin)
        
        url = reverse('topics:topic-subtopics', kwargs={'topic_id': test_topic.id})
        data = {
            'name': 'New Subtopic',
            'topic': test_topic.id
        }
        response = api_client.post(url, data)
        
        assert response.status_code == 201
        assert Subtopic.objects.count() == 1
        assert Subtopic.objects.first().name == 'New Subtopic'

    @pytest.fixture
    def test_topic(self, db):
        return Topic.objects.create(name='Python', description='Python programming')
