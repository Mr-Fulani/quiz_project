import logging
import time
from datetime import timedelta, datetime
from django.contrib.auth import login
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.utils.http import http_date
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
            logger.info(f"=== TELEGRAM AUTH GET REQUEST ===")
            logger.info(f"Request method: {request.method}")
            logger.info(f"Request GET params: {dict(request.GET)}")
            logger.info(f"Request POST params: {dict(request.POST)}")
            logger.info(f"Request path: {request.path}")
            logger.info(f"Request full path: {request.get_full_path()}")
            logger.info(f"Request query string: {request.META.get('QUERY_STRING', '')}")
            logger.info(f"Request host: {request.get_host()}")
            logger.info(f"Request referer: {request.META.get('HTTP_REFERER', 'N/A')}")
            logger.info(f"Request user agent: {request.META.get('HTTP_USER_AGENT', 'N/A')}")
            
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
            raw_data = {}
            
            # Обрабатываем GET параметры - QueryDict возвращает списки
            for key, value in request.GET.items():
                if isinstance(value, list) and len(value) > 0:
                    raw_data[key] = value[0]
                elif value:
                    raw_data[key] = value
            
            # Также проверяем POST на случай если Telegram отправляет через POST
            if request.method == 'POST' and request.POST:
                logger.info("Обнаружены данные в POST, добавляем к GET данным")
                for key, value in request.POST.items():
                    if isinstance(value, list) and len(value) > 0:
                        raw_data[key] = value[0]
                    elif value:
                        raw_data[key] = value
            
            logger.info(f"Raw data (обработанные): {raw_data}")
            logger.info(f"Raw data keys: {list(raw_data.keys())}")
            
            # Дополнительная проверка: может быть данные в request.body или request.META
            if request.body:
                try:
                    body_str = request.body.decode('utf-8')
                    logger.info(f"Request body (decoded): {body_str[:500]}")
                except Exception as e:
                    logger.warning(f"Не удалось декодировать body: {e}")
            
            logger.info(f"Request content_type: {request.content_type}")
            
            # Проверяем, есть ли вообще данные от Telegram
            if not raw_data or 'id' not in raw_data:
                logger.error("=" * 60)
                logger.error("❌ НЕТ ДАННЫХ ОТ TELEGRAM ВИДЖЕТА!")
                logger.error("=" * 60)
                logger.error(f"Request method: {request.method}")
                logger.error(f"Request path: {request.path}")
                logger.error(f"Request full path: {request.get_full_path()}")
                logger.error(f"Request query string: {request.META.get('QUERY_STRING', 'ПУСТО')}")
                logger.error(f"Request GET: {dict(request.GET)}")
                logger.error(f"Request POST: {dict(request.POST)}")
                logger.error(f"Request body: {request.body}")
                logger.error(f"Все доступные ключи в raw_data: {list(raw_data.keys()) if raw_data else 'НЕТ ДАННЫХ'}")
                logger.error(f"Полный URL: {request.build_absolute_uri()}")
                logger.error(f"Referer: {request.META.get('HTTP_REFERER', 'НЕТ')}")
                logger.error("=" * 60)
                return redirect('/?open_login=true&error=Нет данных от Telegram виджета')
            
            # Преобразуем данные в правильные типы
            data = {}
            for key, value in raw_data.items():
                # Уже обработали списки выше, но на всякий случай проверяем
                if isinstance(value, list):
                    val = value[0] if len(value) > 0 else ''
                else:
                    val = value
                
                # Пропускаем пустые значения для необязательных полей
                if val is None or val == '':
                    if key in ['id', 'auth_date', 'hash']:
                        # Обязательные поля не могут быть пустыми
                        logger.error(f"Обязательное поле {key} пустое или отсутствует")
                        return redirect('/?open_login=true&error=Неверный формат данных')
                    continue
                
                # Преобразуем в нужные типы согласно сериализатору
                if key == 'id':
                    try:
                        data[key] = int(val)
                    except (ValueError, TypeError) as e:
                        logger.error(f"Ошибка преобразования id в int: {e}, значение: {val}")
                        return redirect('/?open_login=true&error=Неверный формат данных')
                elif key == 'auth_date':
                    try:
                        data[key] = int(val)
                    except (ValueError, TypeError) as e:
                        logger.error(f"Ошибка преобразования auth_date в int: {e}, значение: {val}")
                        return redirect('/?open_login=true&error=Неверный формат данных')
                else:
                    # Остальные поля - строки
                    data[key] = str(val) if val else ''
            
            logger.info(f"Преобразованные данные для валидации: {data}")
            
            # Валидируем данные перед обработкой
            serializer = TelegramAuthSerializer(data=data)
            if not serializer.is_valid():
                logger.error(f"Ошибка валидации: {serializer.errors}")
                return redirect('/?open_login=true&error=Неверные данные авторизации')
            
            logger.info(f"Данные прошли валидацию: {serializer.validated_data}")
            
            # Обрабатываем авторизацию с валидированными данными
            result = TelegramAuthService.process_telegram_auth(serializer.validated_data, request)
            
            logger.info(f"Результат обработки авторизации: success={result.get('success') if result else False}")
            
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
            
            # Проверяем что сессия создана и сохранена в БД
            session_key = request.session.session_key
            logger.info(f"Сессия после login: session_key={session_key}")
            
            # Проверяем наличие сессии в БД
            if session_key:
                from django.contrib.sessions.models import Session
                try:
                    session_exists = Session.objects.filter(session_key=session_key).exists()
                    logger.info(f"Проверка сессии в БД: session_exists={session_exists}, session_key={session_key}")
                    if not session_exists:
                        logger.warning(f"⚠️ Сессия {session_key} не найдена в БД! Возможно проблема с SESSION_ENGINE или Redis")
                        # Пытаемся сохранить еще раз
                        request.session.save()
                        session_exists_retry = Session.objects.filter(session_key=session_key).exists()
                        logger.info(f"Повторная проверка после save(): session_exists={session_exists_retry}")
                except Exception as e:
                    logger.error(f"Ошибка при проверке сессии в БД: {e}")
            
            # Устанавливаем куки явно для обеспечения сохранения сессии
            response = redirect('/?telegram_auth_success=true')
            
            # Копируем куки сессии в response для гарантированного сохранения
            if session_key:
                max_age = getattr(settings, 'SESSION_COOKIE_AGE', None)
                expires = None
                if max_age:
                    expires = http_date(time.time() + max_age)
                
                response.set_cookie(
                    settings.SESSION_COOKIE_NAME,
                    session_key,
                    max_age=max_age,
                    expires=expires,
                    domain=getattr(settings, 'SESSION_COOKIE_DOMAIN', None),
                    path=getattr(settings, 'SESSION_COOKIE_PATH', '/'),
                    secure=getattr(settings, 'SESSION_COOKIE_SECURE', False) if not settings.DEBUG else False,
                    httponly=getattr(settings, 'SESSION_COOKIE_HTTPONLY', True),
                    samesite=getattr(settings, 'SESSION_COOKIE_SAMESITE', 'Lax')
                )
            
            logger.info(f"Пользователь {user.username} успешно авторизован через Telegram, session_key={session_key}")
            
            # Проверяем, если запрос пришел из iframe (виджет Telegram)
            # В этом случае возвращаем HTML страницу, которая закроет окно и обновит родительскую страницу
            if request.headers.get('Sec-Fetch-Dest') == 'iframe' or 'iframe' in request.headers.get('Referer', '').lower():
                from django.shortcuts import render
                logger.info("Запрос пришел из iframe, возвращаем HTML страницу для закрытия окна")
                return render(request, 'social_auth/telegram_auth_success.html', {
                    'user': user,
                    'session_key': session_key
                })
            
            return response
            
        except Exception as e:
            import traceback
            logger.error(f"Критическая ошибка в GET TelegramAuthView: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            logger.error(f"Request: method={request.method}, path={request.path}, GET={dict(request.GET)}")
            error_message = 'Внутренняя ошибка сервера при авторизации'
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
            
            # Устанавливаем куки явно для обеспечения сохранения сессии
            response = redirect('/?telegram_auth_success=true&mock=true')
            
            # Копируем куки сессии в response для гарантированного сохранения
            session_key = request.session.session_key
            if session_key:
                max_age = getattr(settings, 'SESSION_COOKIE_AGE', None)
                expires = None
                if max_age:
                    expires = http_date(time.time() + max_age)
                
                response.set_cookie(
                    settings.SESSION_COOKIE_NAME,
                    session_key,
                    max_age=max_age,
                    expires=expires,
                    domain=getattr(settings, 'SESSION_COOKIE_DOMAIN', None),
                    path=getattr(settings, 'SESSION_COOKIE_PATH', '/'),
                    secure=getattr(settings, 'SESSION_COOKIE_SECURE', False) if not settings.DEBUG else False,
                    httponly=getattr(settings, 'SESSION_COOKIE_HTTPONLY', True),
                    samesite=getattr(settings, 'SESSION_COOKIE_SAMESITE', 'Lax')
                )
            
            logger.info(f"Мок авторизация: пользователь {user.username} авторизован, session_key={session_key}")
            
            return response
            
        except Exception as e:
            logger.error(f"Ошибка в мок авторизации: {e}")
            return redirect('/?open_login=true&error=Ошибка мок авторизации')

    def post(self, request, *args, **kwargs):
        """
        Обрабатывает POST запрос с данными от Telegram Login Widget.
        """
        try:
            logger.info(f"=== TELEGRAM AUTH POST REQUEST ===")
            if hasattr(request, 'data'):
                logger.info(f"Request data (DRF): {request.data}")
            logger.info(f"Request POST params: {dict(request.POST)}")
            if request.body:
                try:
                    logger.info(f"Request body (first 500 chars): {request.body.decode('utf-8')[:500]}")
                except Exception:
                    logger.info(f"Request body (raw, first 500 bytes): {request.body[:500]}")
            logger.info(f"Request path: {request.path}")
            logger.info(f"Request host: {request.get_host()}")
            logger.info(f"Request referer: {request.META.get('HTTP_REFERER', 'N/A')}")
            
            # Обрабатываем данные из request.data (DRF) или request.POST
            auth_data = {}
            if hasattr(request, 'data') and request.data:
                auth_data = dict(request.data)
            elif request.POST:
                # Обрабатываем QueryDict
                for key, value in request.POST.items():
                    if isinstance(value, list) and len(value) > 0:
                        auth_data[key] = value[0]
                    elif value:
                        auth_data[key] = value
            else:
                # Пытаемся парсить JSON из body
                try:
                    import json
                    if request.body:
                        auth_data = json.loads(request.body.decode('utf-8'))
                except Exception as e:
                    logger.warning(f"Не удалось распарсить JSON из body: {e}")
            
            logger.info(f"Обработанные данные авторизации: {auth_data}")
            
            # Проверяем мок запросы на продакшене
            if auth_data.get('mock') == 'true':
                if not getattr(settings, 'MOCK_TELEGRAM_AUTH', False):
                    logger.warning("Попытка POST мок авторизации на продакшене")
                    return Response({
                        'success': False,
                        'error': 'Мок авторизация недоступна на продакшене'
                    }, status=status.HTTP_403_FORBIDDEN)
            
            # Проверяем режим мока (только для разработки)
            if (getattr(settings, 'MOCK_TELEGRAM_AUTH', False) and 
                auth_data.get('mock') == 'true'):
                return self._handle_mock_post(request)
            
            # Валидируем данные
            logger.info(f"Валидация данных: {auth_data}")
            serializer = TelegramAuthSerializer(data=auth_data)
            if not serializer.is_valid():
                logger.error(f"Ошибка валидации POST данных: {serializer.errors}")
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
            
            logger.info(f"Результат обработки POST авторизации: success={result.get('success') if result else False}")
            
            if not result or not result.get('success'):
                return Response({
                    'success': False,
                    'error': result.get('error', 'Ошибка авторизации')
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Авторизуем пользователя
            user = result['user']
            
            # Убеждаемся что пользователь активен
            if not user.is_active:
                logger.warning(f"Попытка POST авторизации неактивного пользователя: {user.username}")
                return Response({
                    'success': False,
                    'error': 'Аккаунт неактивен'
                }, status=status.HTTP_403_FORBIDDEN)
            
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            
            # Явно сохраняем сессию
            request.session.save()
            
            # Проверяем что сессия создана и сохранена в БД
            session_key_before = request.session.session_key
            logger.info(f"POST: Сессия после login: session_key={session_key_before}")
            
            # Проверяем наличие сессии в БД
            if session_key_before:
                from django.contrib.sessions.models import Session
                try:
                    session_exists = Session.objects.filter(session_key=session_key_before).exists()
                    logger.info(f"POST: Проверка сессии в БД: session_exists={session_exists}, session_key={session_key_before}")
                    if not session_exists:
                        logger.warning(f"⚠️ POST: Сессия {session_key_before} не найдена в БД! Возможно проблема с SESSION_ENGINE или Redis")
                        # Пытаемся сохранить еще раз
                        request.session.save()
                        session_exists_retry = Session.objects.filter(session_key=session_key_before).exists()
                        logger.info(f"POST: Повторная проверка после save(): session_exists={session_exists_retry}")
                except Exception as e:
                    logger.error(f"POST: Ошибка при проверке сессии в БД: {e}")
            
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
            
            # Создаем Response и устанавливаем куки сессии явно
            response = Response(response_data, status=status.HTTP_200_OK)
            
            # Устанавливаем куки сессии для гарантированного сохранения
            session_key = session_key_before  # Используем уже полученный session_key
            if session_key:
                max_age = getattr(settings, 'SESSION_COOKIE_AGE', None)
                expires = None
                if max_age:
                    expires = http_date(time.time() + max_age)
                
                response.set_cookie(
                    settings.SESSION_COOKIE_NAME,
                    session_key,
                    max_age=max_age,
                    expires=expires,
                    domain=getattr(settings, 'SESSION_COOKIE_DOMAIN', None),
                    path=getattr(settings, 'SESSION_COOKIE_PATH', '/'),
                    secure=getattr(settings, 'SESSION_COOKIE_SECURE', False) if not settings.DEBUG else False,
                    httponly=getattr(settings, 'SESSION_COOKIE_HTTPONLY', True),
                    samesite=getattr(settings, 'SESSION_COOKIE_SAMESITE', 'Lax')
                )
            
            logger.info(f"POST авторизация: пользователь {user.username} успешно авторизован, session_key={session_key}")
            
            return response
            
        except Exception as e:
            import traceback
            logger.error(f"Критическая ошибка в POST TelegramAuthView: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            logger.error(f"Request: method={request.method}, path={request.path}, data={getattr(request, 'data', {})}")
            return Response({
                'success': False,
                'error': 'Внутренняя ошибка сервера при авторизации'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _handle_mock_post(self, request):
        """Обрабатывает POST мок авторизацию"""
        try:
            import time
            # Получаем данные из запроса
            auth_data = {}
            if hasattr(request, 'data') and request.data:
                auth_data = dict(request.data)
            elif request.POST:
                for key, value in request.POST.items():
                    if isinstance(value, list) and len(value) > 0:
                        auth_data[key] = value[0]
                    elif value:
                        auth_data[key] = value
            
            # Получаем данные из запроса, преобразуя в правильные типы
            user_id = auth_data.get('user_id', '975113235')
            try:
                user_id = int(user_id) if isinstance(user_id, str) else user_id
            except (ValueError, TypeError):
                user_id = 975113235
            
            mock_data = {
                'id': user_id,
                'first_name': auth_data.get('first_name', 'TestUser') or '',
                'last_name': auth_data.get('last_name', 'Developer') or '',
                'username': auth_data.get('username', 'testdev') or '',
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


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def telegram_auth_debug(request):
    """
    Временный диагностический endpoint для проверки данных от Telegram.
    """
    import json
    from django.http import JsonResponse
    
    debug_data = {
        'method': request.method,
        'path': request.path,
        'full_path': request.get_full_path(),
        'query_string': request.META.get('QUERY_STRING', ''),
        'get_params': dict(request.GET),
        'post_params': dict(request.POST),
        'body': request.body.decode('utf-8') if request.body else '',
        'content_type': request.content_type,
        'headers': {k: v for k, v in request.META.items() if k.startswith('HTTP_')},
        'referer': request.META.get('HTTP_REFERER', ''),
        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
    }
    
    logger.error("=" * 60)
    logger.error("🔍 DEBUG ENDPOINT - ВСЕ ДАННЫЕ ЗАПРОСА:")
    logger.error(json.dumps(debug_data, indent=2, ensure_ascii=False))
    logger.error("=" * 60)
    
    return JsonResponse(debug_data, json_dumps_params={'ensure_ascii': False, 'indent': 2})


@api_view(['GET'])
@permission_classes([AllowAny])
def telegram_oauth_redirect(request):
    """
    Генерирует прямой URL для Telegram OAuth и делает redirect на него.
    Использует прямой /auth endpoint (не /embed), чтобы открываться в том же окне, а не в iframe.
    """
    logger.info("=" * 60)
    logger.info("🚀 TELEGRAM OAUTH REDIRECT ЗАПРОС")
    logger.info("=" * 60)
    logger.info(f"Request method: {request.method}")
    logger.info(f"Request path: {request.path}")
    logger.info(f"Request host: {request.get_host()}")
    logger.info(f"Request GET params: {dict(request.GET)}")
    logger.info(f"Request headers: {dict(request.headers)}")
    
    try:
        from django.conf import settings
        from urllib.parse import quote
        import requests
        
        bot_username = getattr(settings, 'TELEGRAM_BOT_USERNAME', None)
        bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
        
        if not bot_username:
            logger.error("TELEGRAM_BOT_USERNAME не настроен в settings")
            return redirect('/?open_login=true&error=Настройки Telegram бота не найдены')
        
        # Получаем bot_id из токена через getMe API
        bot_id = None
        if bot_token:
            try:
                response = requests.get(f'https://api.telegram.org/bot{bot_token}/getMe', timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('ok'):
                        bot_id = data.get('result', {}).get('id')
                        logger.info(f"✅ Получен bot_id из API: {bot_id}")
                    else:
                        logger.error(f"❌ Telegram API вернул ошибку: {data}")
                else:
                    logger.error(f"❌ Telegram API вернул статус {response.status_code}: {response.text}")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось получить bot_id из API: {e}")
        
        # Получаем текущий домен
        current_domain = request.get_host()
        protocol = 'https' if request.is_secure() else 'http'
        origin = f"{protocol}://{current_domain}"
        
        # URL для возврата после авторизации
        # ВАЖНО: Telegram передает данные в query параметрах, поэтому URL должен быть без hash
        # ВАЖНО: Если данные не приходят, это означает, что домен не настроен в BotFather
        # Используем URL без trailing slash, так как Telegram может его убрать при редиректе
        return_to = f"{origin}/api/social-auth/telegram/auth"
        
        logger.info(f"🔍 Параметры для Telegram OAuth:")
        logger.info(f"  - bot_username: {bot_username}")
        logger.info(f"  - bot_id: {bot_id}")
        logger.info(f"  - origin: {origin}")
        logger.info(f"  - return_to: {return_to}")
        
        # Формируем URL для Telegram OAuth
        # ПРОБЛЕМА: Telegram не передает данные в query параметрах при редиректе
        # Это означает, что домен не настроен в BotFather или используется неправильный метод
        # Попробуем использовать embed виджет, который передает данные через postMessage
        # Но сначала проверим, может быть проблема в том, что нужно использовать другой формат return_to
        
        # ВАЖНО: Согласно документации Telegram, данные передаются ТОЛЬКО если домен правильно настроен в BotFather
        # И данные передаются в query параметрах в формате: ?id=...&first_name=...&auth_date=...&hash=...
        
        # Попробуем использовать прямой /auth endpoint, но с правильным форматом return_to
        if bot_id:
            # Используем bot_id для прямого /auth endpoint
            # ВАЖНО: return_to должен быть абсолютным URL без trailing slash (по документации Telegram)
            telegram_oauth_url = (
                f"https://oauth.telegram.org/auth?"
                f"bot_id={bot_id}&"
                f"origin={quote(origin)}&"
                f"request_access=write&"
                f"return_to={quote(return_to.rstrip('/'))}"
            )
            logger.info(f"✅ Используется прямой /auth endpoint с bot_id")
            logger.warning(f"⚠️ ВАЖНО: Если данные не приходят, проверьте настройки домена в BotFather!")
            logger.warning(f"⚠️ Домен должен быть настроен через /setdomain в @BotFather")
            logger.warning(f"⚠️ Домен должен быть: {current_domain} (без протокола)")
        else:
            # Fallback: используем embed URL с username (откроется в iframe, но это лучше чем ничего)
            logger.warning("⚠️ bot_id не получен, используем embed URL с username")
            telegram_oauth_url = (
                f"https://oauth.telegram.org/embed/{bot_username}?"
                f"origin={quote(origin)}&"
                f"return_to={quote(return_to.rstrip('/'))}&"
                f"size=large&"
                f"userpic=true&"
                f"request_access=write&"
                f"lang=ru"
            )
        
        logger.info(f"🔗 Redirect на Telegram OAuth: {telegram_oauth_url}")
        logger.info(f"⚠️ ВАЖНО: Убедитесь, что домен {current_domain} настроен в BotFather!")
        logger.info(f"⚠️ Выполните в @BotFather: /setdomain для бота {bot_username}")
        logger.info(f"⚠️ Укажите домен: {current_domain}")
        
        return redirect(telegram_oauth_url)
        
    except Exception as e:
        logger.error(f"Ошибка при генерации Telegram OAuth URL: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return redirect('/?open_login=true&error=Ошибка при генерации URL авторизации')
