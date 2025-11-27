import os
import io
import uuid
import logging

from PIL import Image
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
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
    Синхронизирует основные поля и связанные коллекции (сайты, навыки, опыт и т.д.).
    """
    from blog.models import (
        Resume,
        ResumeWebsite,
        ResumeSkill,
        ResumeWorkHistory,
        ResumeResponsibility,
        ResumeEducation,
        ResumeLanguage,
    )

    data = request.data

    def _replace_simple_collection(model, resume_obj, values, value_key):
        """Полностью пересоздаёт простые связанные коллекции (сайты, навыки)."""
        model.objects.filter(resume=resume_obj).delete()
        bulk_objects = []
        for order, raw_value in enumerate(values or []):
            if not raw_value:
                continue
            kwargs = {'resume': resume_obj, 'order': order}
            kwargs[value_key] = raw_value
            bulk_objects.append(model(**kwargs))
        if bulk_objects:
            model.objects.bulk_create(bulk_objects)

    def _sync_responsibilities(work_obj, resp_en, resp_ru):
        """Обновляет обязанности внутри записи опыта работы."""
        existing = list(work_obj.responsibilities.all().order_by('order', 'id'))
        keep_ids = []
        max_len = max(len(resp_en or []), len(resp_ru or []))
        for idx in range(max_len):
            text_en = resp_en[idx] if idx < len(resp_en or []) else ''
            text_ru = resp_ru[idx] if idx < len(resp_ru or []) else ''
            if idx < len(existing):
                resp_obj = existing[idx]
                resp_obj.text_en = text_en
                resp_obj.text_ru = text_ru
                resp_obj.order = idx
                resp_obj.save()
            else:
                resp_obj = ResumeResponsibility.objects.create(
                    work_history=work_obj,
                    text_en=text_en,
                    text_ru=text_ru,
                    order=idx
                )
            keep_ids.append(resp_obj.id)
        if keep_ids:
            work_obj.responsibilities.exclude(id__in=keep_ids).delete()
        else:
            work_obj.responsibilities.all().delete()

    def _sync_work_history(resume_obj, work_items):
        """Обновляет записи опыта работы, не трогая лишние элементы."""
        existing = list(resume_obj.work_history_items.all().order_by('order', 'id'))
        for idx, work_payload in enumerate(work_items or []):
            work_obj = existing[idx] if idx < len(existing) else ResumeWorkHistory(resume=resume_obj)
            work_obj.title_en = work_payload.get('title_en', '')
            work_obj.title_ru = work_payload.get('title_ru', '')
            work_obj.period_en = work_payload.get('period_en', '')
            work_obj.period_ru = work_payload.get('period_ru', '')
            work_obj.company_en = work_payload.get('company_en', '')
            work_obj.company_ru = work_payload.get('company_ru', '')
            work_obj.order = idx
            work_obj.save()
            _sync_responsibilities(
                work_obj,
                work_payload.get('responsibilities_en'),
                work_payload.get('responsibilities_ru')
            )

    def _replace_complex_collection(model, resume_obj, payload, field_mapping):
        """
        Полностью пересоздаёт коллекции, которые заполняются целиком (образование, языки).
        field_mapping задаёт соответствие ключей payload -> полей модели.
        """
        model.objects.filter(resume=resume_obj).delete()
        new_objects = []
        for order, item in enumerate(payload or []):
            if not isinstance(item, dict):
                continue
            kwargs = {'resume': resume_obj, 'order': order}
            for payload_key, model_field in field_mapping.items():
                kwargs[model_field] = item.get(payload_key, '')
            new_objects.append(model(**kwargs))
        if new_objects:
            model.objects.bulk_create(new_objects)

    try:
        with transaction.atomic():
            resume, created = Resume.objects.get_or_create(
                is_active=True,
                defaults={
                    'name': data.get('name', ''),
                    'contact_info_en': data.get('contact_info_en', ''),
                    'contact_info_ru': data.get('contact_info_ru', ''),
                    'email': data.get('email', ''),
                    'summary_en': data.get('summary_en', ''),
                    'summary_ru': data.get('summary_ru', ''),
                    'websites': data.get('websites', []),
                    'skills': data.get('skills', []),
                    'work_history': data.get('work_history', []),
                    'education': data.get('education', []),
                    'languages': data.get('languages', []),
                }
            )

            updatable_fields = (
                'name',
                'contact_info_en',
                'contact_info_ru',
                'email',
                'summary_en',
                'summary_ru',
                'websites',
                'skills',
                'work_history',
                'education',
                'languages',
            )
            for field in updatable_fields:
                if field in data:
                    setattr(resume, field, data.get(field, getattr(resume, field)))
            if not created:
                resume.save()

            if isinstance(data.get('websites'), list):
                _replace_simple_collection(ResumeWebsite, resume, data['websites'], 'url')

            if isinstance(data.get('skills'), list):
                _replace_simple_collection(ResumeSkill, resume, data['skills'], 'name')

            if isinstance(data.get('work_history'), list):
                _sync_work_history(resume, data['work_history'])

            if isinstance(data.get('education'), list):
                _replace_complex_collection(
                    ResumeEducation,
                    resume,
                    data['education'],
                    {
                        'title_en': 'title_en',
                        'title_ru': 'title_ru',
                        'period_en': 'period_en',
                        'period_ru': 'period_ru',
                        'institution_en': 'institution_en',
                        'institution_ru': 'institution_ru',
                    }
                )

            if isinstance(data.get('languages'), list):
                _replace_complex_collection(
                    ResumeLanguage,
                    resume,
                    data['languages'],
                    {
                        'name_en': 'name_en',
                        'name_ru': 'name_ru',
                        'level': 'level',
                    }
                )

        logger.info(f"Резюме успешно сохранено пользователем {request.user.username}")
        return Response({
            'success': True,
            'message': 'Резюме успешно сохранено',
            'resume_id': resume.id
        })

    except Exception as exc:
        logger.error(f"Ошибка при сохранении резюме: {exc}")
        return Response({
            'success': False,
            'error': f'Ошибка при сохранении: {exc}'
        }, status=500)