import pytest
from django.contrib.auth import get_user_model
from feedback.models import FeedbackMessage
from feedback.serializers import FeedbackSerializer

User = get_user_model()

@pytest.mark.django_db
class TestFeedbackSerializer:
    @pytest.fixture
    def test_user(self):
        return User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

    def test_serialization(self):
        feedback = FeedbackMessage.objects.create(
            user_id=123456789,
            username='test_user',
            message='Test feedback message'
        )
        serializer = FeedbackSerializer(feedback)
        data = serializer.data

        assert data['user_id'] == 123456789
        assert data['username'] == 'test_user'
        assert data['message'] == 'Test feedback message'
        assert data['is_processed'] is False
        assert 'created_at' in data
        assert 'short_message' in data

    def test_deserialization_valid_data(self):
        data = {
            'user_id': 123456789,
            'username': 'test_user',
            'message': 'New feedback message'
        }
        serializer = FeedbackSerializer(data=data)
        assert serializer.is_valid()
        feedback = serializer.save()
        assert feedback.user_id == 123456789
        assert feedback.message == 'New feedback message'

    def test_deserialization_with_authenticated_user(self, test_user):
        data = {
            'user_id': test_user.id,
            'message': 'Feedback from authenticated user'
        }
        context = {'request': type('Request', (), {'user': test_user, 'is_authenticated': True})}
        serializer = FeedbackSerializer(data=data, context=context)
        
        assert serializer.is_valid()
        feedback = serializer.save()
        assert feedback.user_id == test_user.id
        assert feedback.username == test_user.username
        assert feedback.message == 'Feedback from authenticated user'

    def test_read_only_fields(self):
        data = {
            'user_id': 123456789,
            'username': 'test_user',
            'message': 'Test message',
            'is_processed': True,
            'created_at': '2023-01-01T00:00:00Z'
        }
        serializer = FeedbackSerializer(data=data)
        assert serializer.is_valid()
        feedback = serializer.save()
        assert feedback.is_processed is False
        assert feedback.created_at is not None

    def test_missing_required_fields(self):
        data = {}
        serializer = FeedbackSerializer(data=data)
        assert not serializer.is_valid()
        assert 'message' in serializer.errors
        assert 'user_id' in serializer.errors

    def test_short_message_field(self):
        long_message = 'This is a very long message that should be truncated ' * 5
        feedback = FeedbackMessage.objects.create(
            user_id=123456789,
            username='test_user',
            message=long_message
        )
        serializer = FeedbackSerializer(feedback)
        assert len(serializer.data['short_message']) <= 100
        assert serializer.data['short_message'].endswith('...') 