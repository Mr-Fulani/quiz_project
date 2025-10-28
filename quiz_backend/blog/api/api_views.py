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


@api_view(['POST'])
@permission_classes([permissions.IsAdminUser])
def save_resume_api(request):
    """
    API для сохранения данных резюме (только для администраторов).
    Сохраняет данные из формы редактирования в БД.
    """
    from blog.models import Resume
    
    try:
        # Получаем или создаем активное резюме
        resume, created = Resume.objects.get_or_create(
            is_active=True,
            defaults={
                'name': request.data.get('name', ''),
                'contact_info_en': request.data.get('contact_info_en', ''),
                'contact_info_ru': request.data.get('contact_info_ru', ''),
                'email': request.data.get('email', ''),
                'websites': request.data.get('websites', []),
                'summary_en': request.data.get('summary_en', ''),
                'summary_ru': request.data.get('summary_ru', ''),
                'skills': request.data.get('skills', []),
                'work_history': request.data.get('work_history', []),
                'education': request.data.get('education', []),
                'languages': request.data.get('languages', []),
            }
        )
        
        if not created:
            # Обновляем существующее резюме
            resume.name = request.data.get('name', resume.name)
            resume.contact_info_en = request.data.get('contact_info_en', resume.contact_info_en)
            resume.contact_info_ru = request.data.get('contact_info_ru', resume.contact_info_ru)
            resume.email = request.data.get('email', resume.email)
            resume.websites = request.data.get('websites', resume.websites)
            resume.summary_en = request.data.get('summary_en', resume.summary_en)
            resume.summary_ru = request.data.get('summary_ru', resume.summary_ru)
            resume.skills = request.data.get('skills', resume.skills)
            resume.work_history = request.data.get('work_history', resume.work_history)
            resume.education = request.data.get('education', resume.education)
            resume.languages = request.data.get('languages', resume.languages)
            resume.save()
        
        logger.info(f"Резюме успешно сохранено пользователем {request.user.username}")
        return Response({
            'success': True,
            'message': 'Резюме успешно сохранено',
            'resume_id': resume.id
        })
        
    except Exception as e:
        logger.error(f"Ошибка при сохранении резюме: {e}")
        return Response({
            'success': False,
            'error': f'Ошибка при сохранении: {str(e)}'
        }, status=500) 