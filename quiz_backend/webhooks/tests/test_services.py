import pytest
from unittest.mock import patch, MagicMock
from webhooks.services import TelegramWebhookHandler

@pytest.mark.django_db
class TestTelegramWebhookHandler:
    @pytest.fixture
    def handler(self):
        return TelegramWebhookHandler()

    def test_process_message_command(self, handler):
        message = {
            'message_id': 1,
            'chat': {'id': 123456789},
            'text': '/start',
            'from': {'id': 11111, 'username': 'test_user'}
        }
        with patch.object(handler, '_send_welcome_message') as mock_welcome:
            handler._handle_message(message)
            mock_welcome.assert_called_once_with(123456789)

    def test_process_message_help(self, handler):
        message = {
            'message_id': 1,
            'chat': {'id': 123456789},
            'text': '/help',
            'from': {'id': 11111, 'username': 'test_user'}
        }
        with patch.object(handler, '_send_help_message') as mock_help:
            handler._handle_message(message)
            mock_help.assert_called_once_with(123456789)

    def test_process_regular_message(self, handler):
        message = {
            'message_id': 1,
            'chat': {'id': 123456789},
            'text': 'Regular message',
            'from': {'id': 11111, 'username': 'test_user'}
        }
        with patch.object(handler, '_handle_answer') as mock_answer:
            handler._handle_message(message)
            mock_answer.assert_called_once_with(message)

    def test_process_callback_query(self, handler):
        callback_query = {
            'id': '123',
            'message': {
                'chat': {'id': 123456789},
                'message_id': 1
            },
            'data': 'test_data',
            'from': {'id': 11111, 'username': 'test_user'}
        }
        with patch.object(handler, '_handle_callback_query') as mock_callback:
            handler.process_update({'callback_query': callback_query})
            mock_callback.assert_called_once_with(callback_query)

    @patch('requests.post')
    def test_setup_webhook_success(self, mock_post, handler):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = handler.setup_webhook()
        assert result is True
        mock_post.assert_called_once()

    @patch('requests.post')
    def test_setup_webhook_failure(self, mock_post, handler):
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_post.return_value = mock_response

        result = handler.setup_webhook()
        assert result is False
        mock_post.assert_called_once()

    def test_process_update_with_message(self, handler):
        update = {
            'message': {
                'message_id': 1,
                'chat': {'id': 123456789},
                'text': 'Test message',
                'from': {'id': 11111, 'username': 'test_user'}
            }
        }
        with patch.object(handler, '_handle_message') as mock_message:
            handler.process_update(update)
            mock_message.assert_called_once_with(update['message'])

    def test_process_update_without_message_or_callback(self, handler):
        update = {'unknown_type': 'data'}
        # Проверяем, что не возникает ошибок при неизвестном типе обновления
        handler.process_update(update) 