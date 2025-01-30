import pytest
import json
from django.urls import reverse
from unittest.mock import patch

@pytest.mark.django_db
class TestTelegramWebhookViews:
    def test_webhook_valid_signature(self, api_client, telegram_data, settings):
        url = reverse('webhooks:telegram-webhook')
        json_data = json.dumps(telegram_data)
        
        # Добавляем HTTP_ префикс к заголовку
        headers = {'HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN': settings.TELEGRAM_WEBHOOK_SECRET}
        
        with patch('webhooks.views.TelegramWebhookHandler') as mock_handler:
            mock_instance = mock_handler.return_value
            mock_instance.process_update.return_value = None
            
            response = api_client.post(
                url,
                data=json_data,
                content_type='application/json',
                **headers
            )

            assert response.status_code == 200
            assert response.data == {'status': 'ok'}
            mock_instance.process_update.assert_called_once_with(telegram_data)

    def test_webhook_invalid_signature(self, api_client, telegram_data):
        url = reverse('webhooks:telegram-webhook')
        headers = {'HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN': 'invalid_signature'}
        response = api_client.post(
            url,
            data=telegram_data,
            content_type='application/json',
            **headers
        )
        assert response.status_code == 401

    def test_webhook_missing_signature(self, api_client, telegram_data):
        url = reverse('webhooks:telegram-webhook')
        response = api_client.post(
            url,
            data=telegram_data,
            content_type='application/json'
        )
        assert response.status_code == 401

    def test_webhook_invalid_json(self, api_client, settings):
        url = reverse('webhooks:telegram-webhook')
        invalid_data = 'invalid json'
        
        # Добавляем HTTP_ префикс к заголовку
        headers = {'HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN': settings.TELEGRAM_WEBHOOK_SECRET}
        
        response = api_client.post(
            url,
            data=invalid_data,
            content_type='application/json',
            **headers
        )
        
        assert response.status_code == 400
        assert 'Invalid JSON' in response.data['error']

    def test_webhook_setup_unauthorized(self, api_client):
        url = reverse('webhooks:telegram-webhook-setup')
        response = api_client.post(url)
        assert response.status_code == 401

    @patch('webhooks.services.TelegramWebhookHandler.setup_webhook')
    def test_webhook_setup_authorized(self, mock_setup, api_client, test_admin):
        mock_setup.return_value = True
        api_client.force_authenticate(user=test_admin)
        url = reverse('webhooks:telegram-webhook-setup')
        response = api_client.post(url)
        assert response.status_code == 200
        assert response.data == {'status': 'webhook setup successful'}

    @patch('webhooks.services.TelegramWebhookHandler.setup_webhook')
    def test_webhook_setup_failure(self, mock_setup, api_client, test_admin):
        mock_setup.return_value = False
        api_client.force_authenticate(user=test_admin)
        url = reverse('webhooks:telegram-webhook-setup')
        response = api_client.post(url)
        assert response.status_code == 500
        assert 'error' in response.data 