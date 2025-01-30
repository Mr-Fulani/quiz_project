import pytest
import json
import hmac
import hashlib
from django.conf import settings

@pytest.fixture(autouse=True)
def setup_test_settings(settings):
    settings.TELEGRAM_BOT_TOKEN = 'test_token'
    settings.BASE_URL = 'https://test.example.com'
    settings.TELEGRAM_WEBHOOK_SECRET = 'test_secret'

@pytest.fixture
def telegram_data():
    return {
        'message': {
            'message_id': 1,
            'chat': {'id': 123456789},
            'text': '/start',
            'from': {'id': 11111, 'username': 'test_user'}
        }
    }

@pytest.fixture
def make_telegram_signature():
    def _make_signature(data, secret):
        json_data = json.dumps(data).encode()
        return hmac.new(
            secret.encode(),
            msg=json_data,
            digestmod=hashlib.sha256
        ).hexdigest()
    return _make_signature 