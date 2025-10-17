"""
Тесты для Telegram сервиса.
"""
from django.test import TestCase
from unittest.mock import patch, MagicMock
from tasks.services.telegram_service import (
    escape_markdown_v2,
    send_photo,
    send_message,
    send_poll
)


class TelegramServiceTestCase(TestCase):
    """
    Тесты для публикации в Telegram.
    """

    def test_escape_markdown_v2(self):
        """
        Тест экранирования специальных символов для MarkdownV2.
        """
        text = "Test text with special chars: . ! - ="
        escaped = escape_markdown_v2(text)
        
        self.assertIn('\\-', escaped)
        self.assertIn('\\.', escaped)
        self.assertIn('\\!', escaped)
        self.assertIn('\\=', escaped)

    @patch('tasks.services.telegram_service.requests.post')
    @patch('tasks.services.telegram_service.settings')
    def test_send_photo_success(self, mock_settings, mock_post):
        """
        Тест успешной отправки фото.
        """
        mock_settings.TELEGRAM_BOT_TOKEN = 'test_token'
        
        mock_response = MagicMock()
        mock_response.json.return_value = {'ok': True, 'result': {'message_id': 123}}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = send_photo('-1001234567890', 'https://example.com/image.png', 'Test caption')

        self.assertIsNotNone(result)
        self.assertEqual(result['message_id'], 123)
        mock_post.assert_called_once()

    @patch('tasks.services.telegram_service.settings')
    def test_send_photo_without_token(self, mock_settings):
        """
        Тест отправки фото без токена.
        """
        mock_settings.TELEGRAM_BOT_TOKEN = None

        result = send_photo('-1001234567890', 'https://example.com/image.png')

        self.assertIsNone(result)

    @patch('tasks.services.telegram_service.requests.post')
    @patch('tasks.services.telegram_service.settings')
    def test_send_message_success(self, mock_settings, mock_post):
        """
        Тест успешной отправки сообщения.
        """
        mock_settings.TELEGRAM_BOT_TOKEN = 'test_token'
        
        mock_response = MagicMock()
        mock_response.json.return_value = {'ok': True, 'result': {'message_id': 124}}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = send_message('-1001234567890', 'Test message')

        self.assertIsNotNone(result)
        self.assertEqual(result['message_id'], 124)

    @patch('tasks.services.telegram_service.requests.post')
    @patch('tasks.services.telegram_service.settings')
    def test_send_poll_success(self, mock_settings, mock_post):
        """
        Тест успешной отправки опроса.
        """
        mock_settings.TELEGRAM_BOT_TOKEN = 'test_token'
        
        mock_response = MagicMock()
        mock_response.json.return_value = {'ok': True, 'result': {'poll': {'id': 'poll_123'}}}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = send_poll(
            '-1001234567890',
            'What is 2+2?',
            ['3', '4', '5'],
            1,
            'Because math!'
        )

        self.assertIsNotNone(result)
        mock_post.assert_called_once()

    @patch('tasks.services.telegram_service.requests.post')
    @patch('tasks.services.telegram_service.settings')
    def test_send_message_api_error(self, mock_settings, mock_post):
        """
        Тест обработки ошибки API.
        """
        mock_settings.TELEGRAM_BOT_TOKEN = 'test_token'
        
        mock_response = MagicMock()
        mock_response.json.return_value = {'ok': False, 'description': 'Bad Request'}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = send_message('-1001234567890', 'Test message')

        self.assertIsNone(result)

