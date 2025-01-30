import pytest
from django.urls import reverse
from feedback.models import FeedbackMessage  # Исправлено с Feedback на FeedbackMessage

@pytest.mark.django_db
class TestFeedbackEndpoints:
    def test_feedback_list(self, api_client, test_admin):
        api_client.force_authenticate(user=test_admin)
        FeedbackMessage.objects.create(
            user_id=123456789,
            message='Great app!',
            username='test_user'
        )
        FeedbackMessage.objects.create(
            user_id=987654321,
            message='Need more features',
            username='another_user'
        )

        url = reverse('feedback:feedback-list')
        response = api_client.get(url)

        assert response.status_code == 200
        assert len(response.data) == 2
        # Проверяем, что оба сообщения присутствуют в любом порядке
        messages = {item['message'] for item in response.data}
        assert messages == {'Great app!', 'Need more features'}

    def test_feedback_detail(self, api_client, test_admin):
        api_client.force_authenticate(user=test_admin)
        feedback = FeedbackMessage.objects.create(
            user_id=123456789,
            message='Great app!',
            username='test_user'  # Добавлено поле username
        )

        url = reverse('feedback:feedback-detail', kwargs={'pk': feedback.id})
        response = api_client.get(url)

        assert response.status_code == 200
        assert response.data['user_id'] == 123456789
        assert response.data['message'] == 'Great app!'
        assert response.data['username'] == 'test_user'

    def test_create_feedback(self, api_client):
        url = reverse('feedback:feedback-create')
        data = {
            'user_id': 123456789,
            'message': 'New feedback',
            'username': 'test_user'  # Добавлено поле username
        }
        response = api_client.post(url, data)

        assert response.status_code == 201
        assert FeedbackMessage.objects.count() == 1
        feedback = FeedbackMessage.objects.first()
        assert feedback.message == 'New feedback'
        assert feedback.user_id == 123456789

    def test_unauthorized_list_access(self, api_client):
        url = reverse('feedback:feedback-list')
        response = api_client.get(url)
        assert response.status_code == 401

    def test_non_admin_list_access(self, api_client, test_user):
        api_client.force_authenticate(user=test_user)
        url = reverse('feedback:feedback-list')
        response = api_client.get(url)
        assert response.status_code == 403

    def test_create_feedback_no_auth(self, api_client):
        url = reverse('feedback:feedback-create')
        data = {
            'user_id': 123456789,
            'message': 'New feedback',
            'username': 'test_user'  # Добавлено поле username
        }
        response = api_client.post(url, data)
        assert response.status_code == 201 