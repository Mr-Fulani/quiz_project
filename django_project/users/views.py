from django.shortcuts import render, get_object_or_404, redirect
from django.template.loader import render_to_string
from django.http import HttpResponse, Http404, JsonResponse
from django.views.decorators.http import require_POST
from django.conf import settings
from .models import User, UserChannelSubscription
import logging

logger = logging.getLogger(__name__)

def user_profile(request, telegram_id):
    """
    Отображает профиль пользователя.
    """
    user = get_object_or_404(User, telegram_id=telegram_id)
    subscriptions = UserChannelSubscription.objects.filter(
        user=user,
        subscription_status=True
    )
    
    context = {
        'user': user,
        'subscriptions': subscriptions,
        'total_tasks': user.statistics.count() if hasattr(user, 'statistics') else 0,
        'successful_tasks': user.statistics.filter(successful=True).count() if hasattr(user, 'statistics') else 0,
        'MEDIA_URL': settings.MEDIA_URL,
    }
    
    return render(request, 'users/profile.html', context)

def load_section(request, section_name):
    """
    Загружает содержимое секции по AJAX запросу.
    """
    telegram_id = request.GET.get('telegram_id')
    if not telegram_id:
        return HttpResponse('Telegram ID не указан', status=400)
        
    try:
        user = get_object_or_404(User, telegram_id=telegram_id)
        context = {
            'user': user,
            'total_tasks': 0,  # Здесь добавьте реальные данные
            'successful_tasks': 0,  # Здесь добавьте реальные данные
            'MEDIA_URL': settings.MEDIA_URL,
        }
        
        template_name = f'users/sections/{section_name}.html'
        html = render_to_string(template_name, context, request)
        return HttpResponse(html)
    except Exception as e:
        return HttpResponse(f'Ошибка: {str(e)}', status=500)

@require_POST
def update_profile(request, telegram_id):
    logger.info(f"Получен запрос на обновление профиля для telegram_id={telegram_id}")
    logger.info(f"FILES: {request.FILES}")
    
    user = get_object_or_404(User, telegram_id=telegram_id)
    
    try:
        if 'avatar' in request.FILES:
            file = request.FILES['avatar']
            logger.info(f"Получен файл: {file.name}, размер: {file.size}")
            
            # Генерируем путь для сохранения файла
            filename = f'user_avatars/user_{telegram_id}_{file.name}'
            
            # Сохраняем файл
            from django.core.files.storage import default_storage
            path = default_storage.save(filename, file)
            logger.info(f"Файл сохранен по пути: {path}")
            
            # Сохраняем путь в базе данных
            user.avatar = path
            user.save()
            logger.info(f"Путь к файлу сохранен в базе данных: {user.avatar}")
            
            # Формируем URL для доступа к файлу
            from django.conf import settings
            file_url = settings.MEDIA_URL + path
            
            return JsonResponse({
                'status': 'success',
                'message': 'Профиль успешно обновлен',
                'avatar_url': file_url
            })
        else:
            logger.warning("Файл аватара не найден в запросе")
            
    except Exception as e:
        logger.error(f"Ошибка при обновлении профиля: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)
