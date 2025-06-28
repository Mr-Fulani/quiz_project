import os
import io
import uuid
import logging

from PIL import Image
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Count, Q

from rest_framework.decorators import api_view, permission_classes
from rest_framework import permissions
from rest_framework.response import Response

from tasks.models import TaskStatistics
from accounts.serializers import ProfileSerializer, SocialLinksSerializer

logger = logging.getLogger(__name__)


@csrf_exempt
def tinymce_image_upload(request):
    """Обработчик загрузки изображений для TinyMCE с сжатием."""
    if request.method == 'POST' and request.FILES.get('file'):
        image = request.FILES['file']
        max_size = 5 * 1024 * 1024  # 5 MB
        if image.size > max_size:
            return JsonResponse({'error': 'Файл слишком большой (максимум 5 МБ)'}, status=400)

        # Генерируем уникальное имя файла
        ext = image.name.split('.')[-1].lower()
        if ext not in ['jpg', 'jpeg', 'png']:
            return JsonResponse({'error': 'Недопустимый формат изображения'}, status=400)
        filename = f"{uuid.uuid4()}.jpg"  # Сохраняем как JPEG
        upload_path = os.path.join('tinymce_uploads', filename)
        full_path = os.path.join(settings.MEDIA_ROOT, upload_path)

        # Сжимаем изображение
        img = Image.open(image)
        img = img.convert('RGB')  # Конвертируем в RGB для JPEG
        if img.width > 800 or img.height > 800:
            img.thumbnail((800, 800), Image.LANCZOS)  # Изменяем размер
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=85, optimize=True)
        output.seek(0)

        # Сохраняем файл
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'wb+') as destination:
            destination.write(output.read())

        # Возвращаем URL изображения
        image_url = f"{settings.MEDIA_URL}{upload_path}"
        return JsonResponse({'location': image_url})

    return JsonResponse({'error': 'Неверный запрос'}, status=400)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def user_profile_stats_api(request):
    """
    API endpoint для получения статистики профиля пользователя для мини-приложения
    """
    try:
        user = request.user
        stats_data = TaskStatistics.get_stats_for_mini_app(user)
        
        if 'error' in stats_data:
            return Response(stats_data, status=500)
            
        return Response(stats_data)
        
    except Exception as e:
        logger.error(f"Ошибка в user_profile_stats_api: {e}")
        return Response({
            'error': 'Не удалось загрузить статистику профиля'
        }, status=500)


@api_view(['GET', 'PATCH'])
@permission_classes([permissions.IsAuthenticated])
def profile_api(request):
    """
    API для получения и обновления профиля пользователя.
    """
    if request.method == 'GET':
        try:
            serializer = ProfileSerializer(request.user, context={'request': request})
            return Response(serializer.data)
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    elif request.method == 'PATCH':
        try:
            serializer = ProfileSerializer(request.user, data=request.data, partial=True, context={'request': request})
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=400)
        except Exception as e:
            return Response({'error': str(e)}, status=500)


@api_view(['GET', 'PATCH'])
@permission_classes([permissions.IsAuthenticated])
def social_links_api(request):
    """
    API для управления социальными сетями пользователя.
    """
    if request.method == 'GET':
        try:
            serializer = SocialLinksSerializer(request.user)
            return Response(serializer.data)
        except Exception as e:
            return Response({'error': str(e)}, status=500)

    elif request.method == 'PATCH':
        try:
            serializer = SocialLinksSerializer(request.user, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response({
                    'success': True,
                    'message': 'Социальные сети обновлены',
                    'data': serializer.data
                })
            return Response({'success': False, 'errors': serializer.errors}, status=400)
        except Exception as e:
            return Response({'error': str(e)}, status=500) 