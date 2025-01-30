import pytest
from django.core.exceptions import ValidationError
from webhooks.models import Webhook, DefaultLink, MainFallbackLink

@pytest.mark.django_db
class TestWebhookModel:
    def test_create_webhook(self):
        webhook = Webhook.objects.create(
            url='https://example.com/webhook',
            service_name='make.com'
        )
        assert webhook.url == 'https://example.com/webhook'
        assert webhook.service_name == 'make.com'
        assert webhook.is_active is True
        assert webhook.created_at is not None
        assert webhook.updated_at is not None

    def test_str_representation(self):
        webhook = Webhook.objects.create(
            url='https://example.com/webhook',
            service_name='make.com'
        )
        assert str(webhook) == 'make.com: https://example.com/webhook'

        # Тест без service_name
        webhook_no_service = Webhook.objects.create(
            url='https://example.com/webhook2'
        )
        assert str(webhook_no_service) == 'Неизвестный сервис: https://example.com/webhook2'

    def test_invalid_url(self):
        with pytest.raises(ValidationError):
            webhook = Webhook(
                url='not_a_url',
                service_name='make.com'
            )
            webhook.full_clean()

@pytest.mark.django_db
class TestDefaultLinkModel:
    def test_create_default_link(self):
        link = DefaultLink.objects.create(
            language='ru',
            topic='python',
            link='https://example.com/python'
        )
        assert link.language == 'ru'
        assert link.topic == 'python'
        assert link.link == 'https://example.com/python'

    def test_str_representation(self):
        link = DefaultLink.objects.create(
            language='ru',
            topic='python',
            link='https://example.com/python'
        )
        assert str(link) == 'ru - python: https://example.com/python'

    def test_unique_language_topic(self):
        DefaultLink.objects.create(
            language='ru',
            topic='python',
            link='https://example.com/python1'
        )
        with pytest.raises(Exception):  # ValidationError или IntegrityError
            DefaultLink.objects.create(
                language='ru',
                topic='python',
                link='https://example.com/python2'
            )

@pytest.mark.django_db
class TestMainFallbackLinkModel:
    def test_create_fallback_link(self):
        link = MainFallbackLink.objects.create(
            language='ru',
            link='https://example.com/fallback'
        )
        assert link.language == 'ru'
        assert link.link == 'https://example.com/fallback'

    def test_str_representation(self):
        link = MainFallbackLink.objects.create(
            language='ru',
            link='https://example.com/fallback'
        )
        assert str(link) == 'Резервная ссылка для ru: https://example.com/fallback'

    def test_unique_language(self):
        MainFallbackLink.objects.create(
            language='ru',
            link='https://example.com/fallback1'
        )
        with pytest.raises(Exception):  # ValidationError или IntegrityError
            MainFallbackLink.objects.create(
                language='ru',
                link='https://example.com/fallback2'
            )

    def test_language_lowercase(self):
        link = MainFallbackLink.objects.create(
            language='RU',
            link='https://example.com/fallback'
        )
        link.full_clean()
        assert link.language == 'ru'  # Проверяем, что язык сохранен в нижнем регистре 