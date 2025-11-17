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
from django.conf import settings

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
    
    Обрабатывает данные от Telegram Login Widget или мок в режиме разработки.
    """
    permission_classes = [AllowAny]
    
    def dispatch(self, request, *args, **kwargs):
        """Отлавливаем все запросы"""
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request, *args, **kwargs):
        """
        Обрабатывает GET запрос с данными от Telegram Login Widget (redirect метод).
        В режиме разработки может обрабатывать мок данные.
        """
        try:
            # Проверяем запросы мока на продакшене
            if (request.GET.get('mock') == 'true' or request.GET.get('mock_auth') == 'true'):
                if not getattr(settings, 'MOCK_TELEGRAM_AUTH', False):
                    # На продакшене мок недоступен
                    logger.warning("Попытка доступа к мок авторизации на продакшене")
                    return redirect('/?open_login=true&error=Мок авторизация недоступна на продакшене')
            
            # Проверяем режим мока (только для разработки)
            if getattr(settings, 'MOCK_TELEGRAM_AUTH', False):
                # Если это запрос на мок страницу
                if request.GET.get('mock') == 'true':
                    return self._handle_mock_page(request)
                
                # Если это запрос с мок данными
                if request.GET.get('mock_auth') == 'true':
                    return self._handle_mock_auth(request)
            
            # Для GET запроса данные приходят в query параметрах
            # QueryDict возвращает списки, нужно извлечь первые значения
            raw_data = dict(request.GET)
            
            # Преобразуем данные в правильные типы
            data = {}
            for key, value in raw_data.items():
                # QueryDict возвращает списки, берем первое значение
                val = value[0] if isinstance(value, list) else value
                
                # Преобразуем в нужные типы согласно сериализатору
                if key == 'id':
                    try:
                        data[key] = int(val)
                    except (ValueError, TypeError):
                        return redirect('/?open_login=true&error=Неверный формат данных')
                elif key == 'auth_date':
                    try:
                        data[key] = int(val)
                    except (ValueError, TypeError):
                        return redirect('/?open_login=true&error=Неверный формат данных')
                else:
                    # Остальные поля - строки
                    data[key] = val if val else ''
            
            # Валидируем данные перед обработкой
            serializer = TelegramAuthSerializer(data=data)
            if not serializer.is_valid():
                return redirect('/?open_login=true&error=Неверные данные авторизации')
            
            # Обрабатываем авторизацию с валидированными данными
            result = TelegramAuthService.process_telegram_auth(serializer.validated_data, request)
            
            if not result or not result.get('success'):
                error_message = result.get('error', 'Ошибка авторизации') if result else 'Ошибка авторизации'
                return redirect(f'/?open_login=true&error={error_message}')
            
            # Авторизуем пользователя
            user = result['user']
            
            # Убеждаемся что пользователь активен
            if not user.is_active:
                logger.warning(f"Попытка авторизации неактивного пользователя: {user.username}")
                return redirect('/?open_login=true&error=Аккаунт неактивен')
            
            # Авторизуем пользователя
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            
            # Явно сохраняем сессию перед редиректом
            request.session.save()
            
            logger.info(f"Пользователь {user.username} успешно авторизован через Telegram")
            
            # Перенаправляем на главную с успешной авторизацией
            return redirect('/?telegram_auth_success=true')
            
        except Exception as e:
            import traceback
            logger.error(f"Ошибка в GET TelegramAuthView: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            error_message = 'Внутренняя ошибка сервера'
            if settings.DEBUG:
                error_message = f'Ошибка: {str(e)}'
            return redirect(f'/?open_login=true&error={error_message}')

    def _handle_mock_page(self, request):
        """Отображает страницу мока для разработки"""
        from django.shortcuts import render
        return render(request, 'blog/telegram_mock.html')
    
    def _handle_mock_auth(self, request):
        """Обрабатывает мок авторизацию"""
        try:
            import time
            # Получаем данные из запроса, преобразуя в правильные типы
            user_id = request.GET.get('user_id', '975113235')
            try:
                user_id = int(user_id)
            except (ValueError, TypeError):
                user_id = 975113235
            
            # Создаем мок данные пользователя
            mock_data = {
                'id': user_id,
                'first_name': request.GET.get('first_name', 'TestUser') or '',
                'last_name': request.GET.get('last_name', 'Developer') or '',
                'username': request.GET.get('username', 'testdev') or '',
                'photo_url': 'https://via.placeholder.com/150',
                'auth_date': int(time.time()),  # Текущее время
                'hash': 'mock_hash_for_development'
            }
            
            # Валидируем данные
            serializer = TelegramAuthSerializer(data=mock_data)
            if not serializer.is_valid():
                return redirect('/?open_login=true&error=Ошибка валидации мок данных')
            
            # Обрабатываем мок авторизацию с валидированными данными
            result = TelegramAuthService.process_telegram_auth(serializer.validated_data, request)
            
            if not result or not result.get('success'):
                return redirect('/?open_login=true&error=Ошибка мок авторизации')
            
            # Авторизуем пользователя
            user = result['user']
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            
            # Явно сохраняем сессию перед редиректом
            request.session.save()
            
            # Перенаправляем на главную с успешной авторизацией
            return redirect('/?telegram_auth_success=true&mock=true')
            
        except Exception as e:
            logger.error(f"Ошибка в мок авторизации: {e}")
            return redirect('/?open_login=true&error=Ошибка мок авторизации')

    def post(self, request, *args, **kwargs):
        """
        Обрабатывает POST запрос с данными от Telegram Login Widget.
        """
        try:
            # Проверяем мок запросы на продакшене
            if request.data.get('mock') == 'true':
                if not getattr(settings, 'MOCK_TELEGRAM_AUTH', False):
                    logger.warning("Попытка POST мок авторизации на продакшене")
                    return Response({
                        'success': False,
                        'error': 'Мок авторизация недоступна на продакшене'
                    }, status=status.HTTP_403_FORBIDDEN)
            
            # Проверяем режим мока (только для разработки)
            if (getattr(settings, 'MOCK_TELEGRAM_AUTH', False) and 
                request.data.get('mock') == 'true'):
                return self._handle_mock_post(request)
            
            # Валидируем данные
            serializer = TelegramAuthSerializer(data=request.data)
            if not serializer.is_valid():
                return Response({
                    'success': False,
                    'error': 'Неверные данные авторизации',
                    'details': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Обрабатываем авторизацию
            result = TelegramAuthService.process_telegram_auth(
                serializer.validated_data, 
                request
            )
            
            if not result or not result.get('success'):
                return Response({
                    'success': False,
                    'error': result.get('error', 'Ошибка авторизации')
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Авторизуем пользователя
            user = result['user']
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            
            # Явно сохраняем сессию
            request.session.save()
            
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
            import traceback
            logger.error(f"Ошибка в TelegramAuthView: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return Response({
                'success': False,
                'error': 'Внутренняя ошибка сервера'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _handle_mock_post(self, request):
        """Обрабатывает POST мок авторизацию"""
        try:
            import time
            # Получаем данные из запроса, преобразуя в правильные типы
            user_id = request.data.get('user_id', '975113235')
            try:
                user_id = int(user_id) if isinstance(user_id, str) else user_id
            except (ValueError, TypeError):
                user_id = 975113235
            
            mock_data = {
                'id': user_id,
                'first_name': request.data.get('first_name', 'TestUser') or '',
                'last_name': request.data.get('last_name', 'Developer') or '',
                'username': request.data.get('username', 'testdev') or '',
                'photo_url': 'https://via.placeholder.com/150',
                'auth_date': int(time.time()),  # Текущее время
                'hash': 'mock_hash_for_development'
            }
            
            # Валидируем данные
            serializer = TelegramAuthSerializer(data=mock_data)
            if not serializer.is_valid():
                return Response({
                    'success': False,
                    'error': 'Ошибка валидации мок данных',
                    'details': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            result = TelegramAuthService.process_telegram_auth(serializer.validated_data, request)
            
            if not result or not result.get('success'):
                return Response({
                    'success': False,
                    'error': 'Ошибка мок авторизации'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            user = result['user']
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            
            # Явно сохраняем сессию
            request.session.save()
            
            return Response({
                'success': True,
                'mock': True,
                'user': UserSocialAccountsSerializer(user).data,
                'message': 'Мок авторизация успешна!'
            })
            
        except Exception as e:
            logger.error(f"Ошибка в POST мок авторизации: {e}")
            return Response({
                'success': False,
                'error': 'Ошибка мок авторизации'
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
