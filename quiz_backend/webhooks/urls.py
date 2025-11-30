from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    WebhookViewSet,
    TelegramWebhookView,
    TelegramWebhookSetupView,
    SocialMediaCallbackView
)

app_name = 'webhooks'

router = DefaultRouter()
router.register('webhooks', WebhookViewSet, basename='webhook')

urlpatterns = [
    path('telegram/', TelegramWebhookView.as_view(), name='telegram-webhook'),
    path('telegram/setup/', TelegramWebhookSetupView.as_view(), name='telegram-webhook-setup'),
    path('social-media-callback/', SocialMediaCallbackView.as_view(), name='social-media-callback'),
] + router.urls 