import pytest
from django.urls import reverse
from webhooks.models import Webhook

@pytest.mark.django_db
class TestWebhookEndpoints:
    def test_webhook_list(self, api_client, test_admin):
        api_client.force_authenticate(user=test_admin)
        webhook1 = Webhook.objects.create(
            url='https://example1.com/webhook',
            service_name='make.com'
        )
        webhook2 = Webhook.objects.create(
            url='https://example2.com/webhook',
            service_name='zapier'
        )

        url = reverse('webhooks:webhook-list')
        response = api_client.get(url)

        assert response.status_code == 200
        assert len(response.data) == 2
        webhooks = {webhook['url'] for webhook in response.data}
        assert webhooks == {'https://example1.com/webhook', 'https://example2.com/webhook'}

    def test_webhook_detail(self, api_client, test_admin):
        api_client.force_authenticate(user=test_admin)
        webhook = Webhook.objects.create(
            url='https://example.com/webhook',
            service_name='make.com'
        )

        url = reverse('webhooks:webhook-detail', kwargs={'pk': webhook.id})
        response = api_client.get(url)

        assert response.status_code == 200
        assert response.data['url'] == 'https://example.com/webhook'
        assert response.data['service_name'] == 'make.com'
        assert response.data['is_active'] is True

    def test_create_webhook(self, api_client, test_admin):
        api_client.force_authenticate(user=test_admin)
        url = reverse('webhooks:webhook-list')
        data = {
            'url': 'https://example.com/webhook',
            'service_name': 'make.com'
        }
        response = api_client.post(url, data)

        assert response.status_code == 201
        assert Webhook.objects.count() == 1
        webhook = Webhook.objects.first()
        assert webhook.url == 'https://example.com/webhook'
        assert webhook.service_name == 'make.com'

    def test_unauthorized_list_access(self, api_client):
        url = reverse('webhooks:webhook-list')
        response = api_client.get(url)
        assert response.status_code == 401

    def test_non_admin_list_access(self, api_client, test_user):
        api_client.force_authenticate(user=test_user)
        url = reverse('webhooks:webhook-list')
        response = api_client.get(url)
        assert response.status_code == 403

    def test_create_webhook_no_auth(self, api_client):
        url = reverse('webhooks:webhook-list')
        data = {
            'url': 'https://example.com/webhook',
            'service_name': 'make.com'
        }
        response = api_client.post(url, data)
        assert response.status_code == 401  # Создание вебхука требует авторизации 