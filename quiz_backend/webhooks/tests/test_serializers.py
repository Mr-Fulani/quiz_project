import pytest
from webhooks.models import Webhook, DefaultLink, MainFallbackLink
from webhooks.serializers import WebhookSerializer, DefaultLinkSerializer, MainFallbackLinkSerializer

@pytest.mark.django_db
class TestWebhookSerializer:
    def test_serialization(self):
        webhook = Webhook.objects.create(
            url='https://example.com/webhook',
            service_name='make.com'
        )
        serializer = WebhookSerializer(webhook)
        data = serializer.data

        assert data['url'] == 'https://example.com/webhook'
        assert data['service_name'] == 'make.com'
        assert data['is_active'] is True
        assert 'created_at' in data
        assert 'updated_at' in data

    def test_deserialization_valid_data(self):
        data = {
            'url': 'https://example.com/webhook',
            'service_name': 'make.com',
            'is_active': True
        }
        serializer = WebhookSerializer(data=data)
        assert serializer.is_valid()
        webhook = serializer.save()
        assert webhook.url == 'https://example.com/webhook'
        assert webhook.service_name == 'make.com'

    def test_invalid_url(self):
        data = {
            'url': 'not_a_url',
            'service_name': 'make.com'
        }
        serializer = WebhookSerializer(data=data)
        assert not serializer.is_valid()
        assert 'url' in serializer.errors

@pytest.mark.django_db
class TestDefaultLinkSerializer:
    def test_serialization(self):
        link = DefaultLink.objects.create(
            language='ru',
            topic='python',
            link='https://example.com/python'
        )
        serializer = DefaultLinkSerializer(link)
        data = serializer.data

        assert data['language'] == 'ru'
        assert data['topic'] == 'python'
        assert data['link'] == 'https://example.com/python'

    def test_deserialization_valid_data(self):
        data = {
            'language': 'ru',
            'topic': 'python',
            'link': 'https://example.com/python'
        }
        serializer = DefaultLinkSerializer(data=data)
        assert serializer.is_valid()
        link = serializer.save()
        assert link.language == 'ru'
        assert link.topic == 'python'

    def test_invalid_link(self):
        data = {
            'language': 'ru',
            'topic': 'python',
            'link': 'not_a_url'
        }
        serializer = DefaultLinkSerializer(data=data)
        assert not serializer.is_valid()
        assert 'link' in serializer.errors

@pytest.mark.django_db
class TestMainFallbackLinkSerializer:
    def test_serialization(self):
        link = MainFallbackLink.objects.create(
            language='ru',
            link='https://example.com/fallback'
        )
        serializer = MainFallbackLinkSerializer(link)
        data = serializer.data

        assert data['language'] == 'ru'
        assert data['link'] == 'https://example.com/fallback'

    def test_deserialization_valid_data(self):
        data = {
            'language': 'RU',  # Проверяем приведение к нижнему регистру
            'link': 'https://example.com/fallback'
        }
        serializer = MainFallbackLinkSerializer(data=data)
        assert serializer.is_valid()
        link = serializer.save()
        assert link.language == 'ru'

    def test_invalid_link(self):
        data = {
            'language': 'ru',
            'link': 'not_a_url'
        }
        serializer = MainFallbackLinkSerializer(data=data)
        assert not serializer.is_valid()
        assert 'link' in serializer.errors

    def test_duplicate_language(self):
        MainFallbackLink.objects.create(
            language='ru',
            link='https://example.com/fallback1'
        )
        data = {
            'language': 'ru',
            'link': 'https://example.com/fallback2'
        }
        serializer = MainFallbackLinkSerializer(data=data)
        assert not serializer.is_valid()
        assert 'language' in serializer.errors 