import pytest
from feedback.models import FeedbackMessage
from django.utils import timezone

@pytest.mark.django_db
class TestFeedbackMessageModel:
    def test_create_feedback(self):
        feedback = FeedbackMessage.objects.create(
            user_id=123456789,
            username='test_user',
            message='Test feedback message'
        )
        assert feedback.user_id == 123456789
        assert feedback.username == 'test_user'
        assert feedback.message == 'Test feedback message'
        assert feedback.is_processed is False  # Проверяем значение по умолчанию
        assert feedback.created_at is not None

    def test_str_representation(self):
        feedback = FeedbackMessage.objects.create(
            user_id=123456789,
            username='test_user',
            message='Test feedback message'
        )
        # Получаем отформатированную дату
        date_str = feedback.created_at.strftime('%Y-%m-%d %H:%M')
        expected_str = f'Сообщение от test_user ({date_str})'
        assert str(feedback) == expected_str

    def test_short_message(self):
        # Тест для короткого сообщения
        feedback = FeedbackMessage.objects.create(
            user_id=123456789,
            username='test_user',
            message='Short message'
        )
        assert feedback.short_message == 'Short message'

        # Тест для длинного сообщения
        long_message = 'This is a very long message that should be truncated in the short_message property' * 3
        feedback = FeedbackMessage.objects.create(
            user_id=987654321,
            username='another_user',
            message=long_message
        )
        assert len(feedback.short_message) <= 100
        assert feedback.short_message.endswith('...')

    def test_ordering(self):
        # Создаем несколько сообщений
        feedback1 = FeedbackMessage.objects.create(
            user_id=123456789,
            username='user1',
            message='First message'
        )
        feedback2 = FeedbackMessage.objects.create(
            user_id=987654321,
            username='user2',
            message='Second message'
        )

        # Проверяем, что они отсортированы по created_at в обратном порядке
        feedbacks = FeedbackMessage.objects.all()
        assert feedbacks[0] == feedback2  # Более новое сообщение должно быть первым
        assert feedbacks[1] == feedback1 