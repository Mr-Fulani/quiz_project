from django.shortcuts import render
import json
import hmac
import hashlib
from django.conf import settings
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status, viewsets
from .services import TelegramWebhookHandler
from .models import Webhook
from .serializers import WebhookSerializer

# Create your views here.

class TelegramWebhookView(APIView):
    """
    Обработчик вебхуков от Telegram.
    
    Проверяет подпись запроса и обрабатывает различные типы обновлений:
    - Новые сообщения
    - Ответы на вопросы
    - Команды бота
    - Действия в группах/каналах
    """
    permission_classes = []  # Публичный endpoint

    def post(self, request, *args, **kwargs):
        # Проверяем подпись запроса
        if not self._verify_telegram_signature(request):
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        try:
            handler = TelegramWebhookHandler()
            update = json.loads(request.body)
            handler.process_update(update)
            return Response({'status': 'ok'})
        except json.JSONDecodeError:
            return Response(
                {'error': 'Invalid JSON'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _verify_telegram_signature(self, request):
        """Проверяет подпись запроса от Telegram."""
        if 'X-Telegram-Bot-Api-Secret-Token' not in request.headers:
            return False
            
        received_token = request.headers['X-Telegram-Bot-Api-Secret-Token']
        
        # Для тестов: если токен совпадает с секретом, считаем подпись валидной
        if received_token == settings.TELEGRAM_WEBHOOK_SECRET:
            return True
            
        return False

class TelegramWebhookSetupView(APIView):
    """
    Настройка вебхука в Telegram Bot API.
    Только для администраторов.
    """
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        try:
            handler = TelegramWebhookHandler()
            success = handler.setup_webhook()
            if success:
                return Response({'status': 'webhook setup successful'})
            return Response(
                {'error': 'Failed to setup webhook'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class WebhookViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления вебхуками.
    """
    queryset = Webhook.objects.all()
    serializer_class = WebhookSerializer
    permission_classes = [permissions.IsAdminUser]

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.IsAuthenticated()]
        return super().get_permissions()
