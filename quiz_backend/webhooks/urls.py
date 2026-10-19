from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    WebhookViewSet,
    SocialMediaCallbackView
)
app_name = 'webhooks'

router = DefaultRouter()
router.register('webhooks', WebhookViewSet, basename='webhook')

urlpatterns = [
    path('social-media-callback/', SocialMediaCallbackView.as_view(), name='social-media-callback'),
] + router.urls 