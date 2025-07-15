import logging
from django.contrib.auth import login
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils.translation import gettext as _

from .serializers import (
    TelegramAuthSerializer, SocialAccountSerializer, 
    UserSocialAccountsSerializer, SocialAuthResponseSerializer
)
from .services import TelegramAuthService, SocialAuthService
from .models import SocialAccount, SocialAuthSettings

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class TelegramAuthView(APIView):
    """
    View для авторизации через Telegram.
    
    Обрабатывает данные от Telegram Login Widget.
    """
    permission_classes = [AllowAny]
    
    def post(self, request, *args, **kwargs):
        """
        Обрабатывает POST запрос с данными от Telegram Login Widget.
        """
        try:
            logger.info(f"Получен запрос авторизации Telegram: {request.data}")
            
            # Валидируем данные
            serializer = TelegramAuthSerializer(data=request.data)
            logger.info(f"Данные для валидации: {request.data}")
            if not serializer.is_valid():
                logger.error(f"Ошибка валидации сериализатора: {serializer.errors}")
                logger.error(f"Ошибка валидации: {serializer.errors}")
                return Response({
                    'success': False,
                    'error': 'Неверные данные авторизации',
                    'details': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            logger.info(f"Данные прошли валидацию: {serializer.validated_data}")
            
            # Обрабатываем авторизацию
            result = TelegramAuthService.process_telegram_auth(
                serializer.validated_data, 
                request
            )
            
            logger.info(f"Результат обработки авторизации: {result}")
            
            if not result or not result.get('success'):
                return Response({
                    'success': False,
                    'error': result.get('error', 'Ошибка авторизации')
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Авторизуем пользователя
            user = result['user']
            login(request, user)
            
            # Подготавливаем ответ
            response_data = {
                'success': True,
                'user': UserSocialAccountsSerializer(user).data,
                'social_account': SocialAccountSerializer(result['social_account']).data,
                'is_new_user': result.get('is_new_user', False),
                'message': _('Успешная авторизация через Telegram') if not result.get('is_new_user') else _('Добро пожаловать! Ваш аккаунт создан.')
            }
            
            # Добавляем redirect_url если есть
            next_url = request.POST.get('next') or request.GET.get('next')
            if next_url:
                response_data['redirect_url'] = next_url
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Детальная ошибка в TelegramAuthView: {e}")
            logger.error(f"Тип ошибки: {type(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            logger.error(f"Ошибка в TelegramAuthView: {e}")
            return Response({
                'success': False,
                'error': 'Внутренняя ошибка сервера'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_social_accounts(request):
    """
    Возвращает социальные аккаунты текущего пользователя.
    """
    try:
        user = request.user
        social_accounts = SocialAuthService.get_user_social_accounts(user)
        
        serializer = UserSocialAccountsSerializer(user)
        return Response({
            'success': True,
            'data': serializer.data
        })
        
    except Exception as e:
        logger.error(f"Ошибка при получении социальных аккаунтов: {e}")
        return Response({
            'success': False,
            'error': 'Ошибка при получении данных'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def disconnect_social_account(request, provider):
    """
    Отключает социальный аккаунт пользователя.
    """
    try:
        user = request.user
        success = SocialAuthService.disconnect_social_account(user, provider)
        
        if success:
            return Response({
                'success': True,
                'message': _('Социальный аккаунт успешно отключен')
            })
        else:
            return Response({
                'success': False,
                'error': _('Аккаунт не найден или уже отключен')
            }, status=status.HTTP_404_NOT_FOUND)
            
    except Exception as e:
        logger.error(f"Ошибка при отключении социального аккаунта: {e}")
        return Response({
            'success': False,
            'error': 'Ошибка при отключении аккаунта'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def enabled_providers(request):
    """
    Возвращает список включенных провайдеров социальной аутентификации.
    """
    try:
        providers = SocialAuthService.get_enabled_providers()
        
        # Получаем дополнительную информацию о провайдерах
        providers_info = []
        for provider in providers:
            provider_info = {
                'provider': provider,
                'name': dict(SocialAccount.PROVIDER_CHOICES).get(provider, provider),
                'auth_url': SocialAuthService.get_auth_url(provider)
            }
            providers_info.append(provider_info)
        
        return Response({
            'success': True,
            'providers': providers_info
        })
        
    except Exception as e:
        logger.error(f"Ошибка при получении провайдеров: {e}")
        return Response({
            'success': False,
            'error': 'Ошибка при получении данных'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@require_http_methods(["GET", "POST"])
def telegram_auth_redirect(request):
    """
    Обработчик для редиректа после авторизации через Telegram.
    
    Используется для обработки данных от Telegram Login Widget
    и перенаправления пользователя.
    """
    try:
        logger.info(f"=== TELEGRAM REDIRECT CALLED ===")
        logger.info(f"Method: {request.method}")
        logger.info(f"URL: {request.build_absolute_uri()}")
        logger.info(f"Headers: {dict(request.headers)}")
        logger.info(f"GET params: {dict(request.GET)}")
        logger.info(f"POST params: {dict(request.POST)}")
        logger.info(f"User-Agent: {request.META.get('HTTP_USER_AGENT', 'Unknown')}")
        logger.info(f"Referer: {request.META.get('HTTP_REFERER', 'Unknown')}")
        
        # Обрабатываем авторизацию (проверяем и POST и GET)
        data = request.POST if request.method == 'POST' else request.GET
        logger.info(f"Telegram redirect: method={request.method}, data={data}")
        result = TelegramAuthService.process_telegram_auth(data, request)
        
        if not result or not result.get('success'):
            # При ошибке перенаправляем на страницу входа с ошибкой
            error_message = result.get('error', 'Ошибка авторизации') if result else 'Ошибка авторизации'
            return redirect(f'/?open_login=true&error={error_message}')
        
        # Авторизуем пользователя
        user = result['user']
        login(request, user)
        
        # Перенаправляем на нужную страницу
        next_url = request.POST.get('next') or request.GET.get('next') or '/'
        
        # Добавляем параметр успешной авторизации
        if '?' in next_url:
            next_url += '&telegram_auth_success=true'
        else:
            next_url += '?telegram_auth_success=true'
        
        return redirect(next_url)
        
    except Exception as e:
        logger.error(f"Ошибка в telegram_auth_redirect: {e}")
        return redirect('/?open_login=true&error=Внутренняя ошибка сервера')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def social_auth_status(request):
    """
    Возвращает статус социальной аутентификации пользователя.
    """
    try:
        user = request.user
        social_accounts = SocialAuthService.get_user_social_accounts(user)
        
        # Проверяем наличие аккаунтов по провайдерам
        status_data = {
            'has_telegram': social_accounts.filter(provider='telegram').exists(),
            'has_github': social_accounts.filter(provider='github').exists(),
            'has_google': social_accounts.filter(provider='google').exists(),
            'has_vk': social_accounts.filter(provider='vk').exists(),
            'total_accounts': social_accounts.count()
        }
        
        return Response({
            'success': True,
            'status': status_data
        })
        
    except Exception as e:
        logger.error(f"Ошибка при получении статуса социальной аутентификации: {e}")
        return Response({
            'success': False,
            'error': 'Ошибка при получении данных'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
