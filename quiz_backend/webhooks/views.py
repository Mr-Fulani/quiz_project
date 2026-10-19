from django.shortcuts import render
import hmac
import hashlib
from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status, viewsets
from .models import Webhook
from .serializers import WebhookSerializer
from tenants.mixins import TenantFilteredViewMixin
import logging

logger = logging.getLogger(__name__)

# Create your views here.

class WebhookViewSet(TenantFilteredViewMixin, viewsets.ModelViewSet):
    """
    ViewSet для управления вебхуками.
    """
    queryset = Webhook.objects.all()
    serializer_class = WebhookSerializer
    # Создание тоже только для админов: вебхук получает данные задач тенанта
    permission_classes = [permissions.IsAdminUser]


class SocialMediaCallbackView(APIView):
    """
    Endpoint для получения статусов публикации от Make.com.
    
    POST /api/webhooks/social-media-callback/
    {
        "task_id": 123,
        "platform": "pinterest",
        "status": "published",
        "post_url": "https://pinterest.com/pin/...",
        "post_id": "123456789",
        "published_at": "2025-11-30T12:05:00Z"
    }
    """
    permission_classes = []  # Публичный endpoint для Make.com
    
    def post(self, request):
        """Обрабатывает обратный вызов от Make.com о статусе публикации."""
        task_id = request.data.get('task_id')
        platform = request.data.get('platform')
        status_value = request.data.get('status')
        post_url = request.data.get('post_url')
        post_id = request.data.get('post_id')
        
        logger.info(f"📥 Получен callback: task_id={task_id}, platform={platform}, status={status_value}")

        # Если задан общий секрет — Make.com обязан прислать его в заголовке
        callback_secret = getattr(settings, 'SOCIAL_MEDIA_CALLBACK_SECRET', '')
        if callback_secret and not hmac.compare_digest(
            request.headers.get('X-Callback-Secret', ''), callback_secret
        ):
            return Response({'error': 'Invalid callback secret'}, status=status.HTTP_403_FORBIDDEN)

        # Без тенанта не трогаем публикации: иначе callback обновил бы запись любого тенанта
        if getattr(request, 'tenant', None) is None:
            return Response({'error': 'Unknown tenant'}, status=status.HTTP_404_NOT_FOUND)

        if not all([task_id, platform, status_value]):
            return Response(
                {'error': 'Missing required fields: task_id, platform, status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from tasks.models import SocialMediaPost
            tenant = getattr(request, 'tenant', None)
            
            # Находим запись о публикации с учетом тенанта
            query = {
                'task_id': task_id,
                'platform': platform
            }
            if tenant:
                query['task__tenant'] = tenant
                
            social_post = SocialMediaPost.objects.filter(**query).order_by('-created_at').first()
            
            if not social_post:
                logger.warning(f"⚠️ SocialMediaPost не найден: task_id={task_id}, platform={platform}")
                return Response(
                    {'error': 'Social media post not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Обновляем статус
            social_post.status = status_value
            
            if status_value == 'published':
                social_post.published_at = timezone.now()
                if post_url:
                    social_post.post_url = post_url
                if post_id:
                    social_post.post_id = post_id
            elif status_value == 'failed':
                social_post.error_message = request.data.get('error_message', 'Неизвестная ошибка')
            
            social_post.save()
            
            logger.info(f"✅ Статус обновлен: task_id={task_id}, platform={platform}, status={status_value}")
            
            return Response({
                'status': 'ok',
                'message': f'Status updated for task {task_id} on {platform}'
            })
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки callback: {e}", exc_info=True)
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
