import logging
import time
from datetime import timedelta, datetime
from django.contrib.auth import login
from django.http import JsonResponse, HttpResponse
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
    UserSocialAccountsSerializer, SocialAuthResponseSerializer,
    GitHubAuthSerializer
)
from .services import TelegramAuthService, SocialAuthService, GitHubAuthService, GoogleAuthService
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

            # Дополнительная отладка для анализа данных от Telegram
            logger.info("=" * 100)
            logger.info("ПОДРОБНЫЙ АНАЛИЗ ЗАПРОСА ОТ TELEGRAM:")
            logger.info("=" * 100)
            logger.info(f"Все GET параметры: {list(request.GET.keys())}")
            for key, value in request.GET.items():
                logger.info(f"  {key}: {value} (type: {type(value)})")

            logger.info(f"Все POST параметры: {list(request.POST.keys())}")
            for key, value in request.POST.items():
                logger.info(f"  {key}: {value} (type: {type(value)})")

            # Проверяем, есть ли Telegram-специфичные параметры
            telegram_params = ['id', 'first_name', 'last_name', 'username', 'photo_url', 'auth_date', 'hash']
            found_telegram_params = [p for p in telegram_params if p in request.GET]
            logger.info(f"Найденные Telegram параметры: {found_telegram_params}")

            if 'id' in request.GET:
                logger.info("✅ Параметр 'id' найден - данные от Telegram присутствуют!")
            else:
                logger.info("❌ Параметр 'id' НЕ найден - данные от Telegram отсутствуют!")
                logger.info("Возможные причины:")
                logger.info("  1. Домен не настроен в BotFather (/setdomain)")
                logger.info("  2. Telegram изменил формат данных")
                logger.info("  3. Проблема с redirect URL")

            logger.info("=" * 100)
            
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
            
            # Дополнительная проверка: может быть данные в _body или request.META
            # НЕ используем request.body напрямую чтобы избежать RawPostDataException
            try:
                if hasattr(request, '_body') and request._body:
                    body_str = request._body.decode('utf-8', errors='ignore')
                    logger.info(f"Request _body (decoded): {body_str[:500]}")
            except Exception as e:
                logger.warning(f"Не удалось декодировать _body: {e}")
            
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
                # НЕ используем request.body напрямую чтобы избежать RawPostDataException
                try:
                    body_info = 'empty'
                    if hasattr(request, '_body') and request._body:
                        body_info = request._body[:500].decode('utf-8', errors='ignore')
                    logger.error(f"Request _body: {body_info}")
                except Exception:
                    logger.error(f"Request _body: cannot read")
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
            # Дублируем вывод в print для гарантии что увидим в логах
            print("=" * 80, flush=True)
            print("=== TELEGRAM AUTH POST REQUEST ===", flush=True)
            print("=" * 80, flush=True)
            
            logger.info("=" * 80)
            logger.info("=== TELEGRAM AUTH POST REQUEST ===")
            logger.info("=" * 80)
            logger.info(f"Request method: {request.method}")
            logger.info(f"Request path: {request.path}")
            logger.info(f"Request host: {request.get_host()}")
            logger.info(f"Request referer: {request.META.get('HTTP_REFERER', 'N/A')}")
            
            print(f"POST Request: {request.method} {request.path}", flush=True)
            
            # Логируем request.data и request.POST (безопасно)
            if hasattr(request, 'data'):
                logger.info(f"Request data (DRF): {request.data}")
                print(f"Request data (DRF): {request.data}", flush=True)
            logger.info(f"Request POST params: {dict(request.POST)}")
            
            # НЕ обращаемся к request.body напрямую - это может вызвать RawPostDataException
            # если body уже был прочитан через request.data
            try:
                if hasattr(request, '_body') and request._body:
                    body_str = request._body.decode('utf-8', errors='ignore')
                    logger.info(f"Request _body (first 500 chars): {body_str[:500]}")
                else:
                    logger.info("Request _body is empty or not accessible")
            except Exception as e:
                logger.warning(f"Не удалось прочитать _body: {e}")
            
            # Обрабатываем данные из request.data (DRF) или request.POST
            # ВАЖНО: В DRF нельзя читать request.body после обращения к request.data!
            # Порядок важен: сначала request.data, потом request.body
            auth_data = {}
            
            # Сначала пробуем request.data (DRF) - это безопасно и не блокирует body
            if hasattr(request, 'data') and request.data:
                try:
                    # request.data может быть QueryDict или dict
                    if hasattr(request.data, 'dict'):
                        auth_data = request.data.dict()
                    else:
                        auth_data = dict(request.data)
                    print(f"Данные получены из request.data (DRF): {auth_data}", flush=True)
                    logger.info(f"Данные получены из request.data (DRF): {auth_data}")
                except Exception as e:
                    error_msg = f"Ошибка при обработке request.data: {e}"
                    print(f"WARNING: {error_msg}", flush=True)
                    logger.warning(error_msg)
            
            # Если не получили из request.data, пробуем request.POST
            if not auth_data and request.POST:
                try:
                    # Обрабатываем QueryDict
                    for key, value in request.POST.items():
                        if isinstance(value, list) and len(value) > 0:
                            auth_data[key] = value[0]
                        elif value:
                            auth_data[key] = value
                    print(f"Данные получены из request.POST: {auth_data}", flush=True)
                    logger.info(f"Данные получены из request.POST: {auth_data}")
                except Exception as e:
                    error_msg = f"Ошибка при обработке request.POST: {e}"
                    print(f"WARNING: {error_msg}", flush=True)
                    logger.warning(error_msg)
            
            # Только если не получили данные из request.data и request.POST, пробуем request.body
            # Но это может вызвать RawPostDataException если body уже был прочитан
            if not auth_data:
                try:
                    # Пытаемся прочитать body только если он еще не был прочитан
                    if hasattr(request, '_body') and request._body:
                        body_str = request._body.decode('utf-8')
                        print(f"Request body (raw from _body): {body_str[:500]}", flush=True)
                        if body_str.strip():
                            import json
                            auth_data = json.loads(body_str)
                            print(f"Данные получены из request._body (JSON): {auth_data}", flush=True)
                            logger.info(f"Данные получены из request._body (JSON): {auth_data}")
                except (AttributeError, json.JSONDecodeError, UnicodeDecodeError) as e:
                    error_msg = f"Не удалось прочитать body: {e}"
                    print(f"WARNING: {error_msg}", flush=True)
                    logger.warning(error_msg)
                except Exception as e:
                    error_msg = f"Ошибка при обработке body: {e}"
                    print(f"WARNING: {error_msg}", flush=True)
                    logger.warning(error_msg)
            
            if not auth_data:
                error_msg = "Не удалось получить данные авторизации ни из одного источника"
                print(f"ERROR: {error_msg}", flush=True)
                logger.error(error_msg)
                return Response({
                    'success': False,
                    'error': 'Отсутствуют данные авторизации'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            print(f"Обработанные данные авторизации: {auth_data}", flush=True)
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
            
            # Преобразуем данные в правильные типы перед валидацией
            processed_data = {}
            for key, value in auth_data.items():
                if key == 'id':
                    try:
                        processed_data[key] = int(value)
                    except (ValueError, TypeError):
                        logger.error(f"Неверный формат id: {value}")
                        return Response({
                            'success': False,
                            'error': 'Неверный формат Telegram ID'
                        }, status=status.HTTP_400_BAD_REQUEST)
                elif key == 'auth_date':
                    try:
                        processed_data[key] = int(value)
                    except (ValueError, TypeError):
                        logger.error(f"Неверный формат auth_date: {value}")
                        return Response({
                            'success': False,
                            'error': 'Неверный формат даты авторизации'
                        }, status=status.HTTP_400_BAD_REQUEST)
                else:
                    processed_data[key] = value if value is not None else ''
            
            logger.info(f"Обработанные данные для валидации: {processed_data}")
            
            # Валидируем данные
            logger.info(f"Валидация данных: {processed_data}")
            serializer = TelegramAuthSerializer(data=processed_data)
            if not serializer.is_valid():
                logger.error(f"Ошибка валидации POST данных: {serializer.errors}")
                return Response({
                    'success': False,
                    'error': 'Неверные данные авторизации',
                    'details': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
            
            logger.info(f"Данные прошли валидацию: {serializer.validated_data}")
            print(f"Данные прошли валидацию: {serializer.validated_data}", flush=True)
            
            # Обрабатываем авторизацию
            print("Вызываем TelegramAuthService.process_telegram_auth...", flush=True)
            result = TelegramAuthService.process_telegram_auth(
                serializer.validated_data, 
                request
            )
            
            result_msg = f"Результат обработки POST авторизации: success={result.get('success') if result else False}"
            print(result_msg, flush=True)
            logger.info(result_msg)
            
            if not result or not result.get('success'):
                return Response({
                    'success': False,
                    'error': result.get('error', 'Ошибка авторизации')
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Авторизуем пользователя
            user = result['user']
            print(f"Пользователь получен: {user.username}, id={user.id}, is_active={user.is_active}", flush=True)
            
            # Убеждаемся что пользователь активен
            if not user.is_active:
                logger.warning(f"Попытка POST авторизации неактивного пользователя: {user.username}")
                print(f"ERROR: Пользователь {user.username} неактивен", flush=True)
                return Response({
                    'success': False,
                    'error': 'Аккаунт неактивен'
                }, status=status.HTTP_403_FORBIDDEN)
            
            print(f"Вызываем login() для пользователя {user.username}...", flush=True)
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            
            # Явно сохраняем сессию
            request.session.save()
            print(f"Сессия сохранена: {request.session.session_key}", flush=True)
            
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
            print("Начинаем сериализацию данных для ответа...", flush=True)
            try:
                user_data = UserSocialAccountsSerializer(user).data
                print(f"Пользователь сериализован: {user.username}", flush=True)
                logger.info(f"Пользователь сериализован: {user.username}")
            except Exception as e:
                import traceback
                error_tb = traceback.format_exc()
                print(f"ERROR сериализации пользователя: {e}", flush=True)
                print(f"Traceback: {error_tb}", flush=True)
                logger.error(f"Ошибка сериализации пользователя: {e}")
                logger.error(f"Traceback: {error_tb}")
                # Fallback: простые данные пользователя
                user_data = {
                    'id': user.id,
                    'username': user.username,
                    'email': getattr(user, 'email', '') or ''
                }
            
            try:
                social_account = result.get('social_account')
                if social_account:
                    social_account_data = SocialAccountSerializer(social_account).data
                    print(f"Social account сериализован: {social_account.provider}", flush=True)
                    logger.info(f"Social account сериализован: {social_account.provider}")
                else:
                    print("WARNING: Social account отсутствует в результате", flush=True)
                    logger.warning("Social account отсутствует в результате")
                    social_account_data = {}
            except Exception as e:
                import traceback
                error_tb = traceback.format_exc()
                print(f"ERROR сериализации social_account: {e}", flush=True)
                print(f"Traceback: {error_tb}", flush=True)
                logger.error(f"Ошибка сериализации social_account: {e}")
                logger.error(f"Traceback: {error_tb}")
                social_account = result.get('social_account')
                if social_account:
                    social_account_data = {
                        'id': social_account.id,
                        'provider': social_account.provider
                    }
                else:
                    social_account_data = {}
            
            # Формируем минимальный ответ чтобы избежать ошибок сериализации
            response_data = {
                'success': True,
                'user': user_data,
                'is_new_user': result.get('is_new_user', False),
            }
            
            # Добавляем social_account только если есть
            if social_account_data:
                response_data['social_account'] = social_account_data
            
            # Добавляем сообщение
            if result.get('is_new_user'):
                response_data['message'] = _('Добро пожаловать! Ваш аккаунт создан.')
            else:
                response_data['message'] = _('Успешная авторизация через Telegram')
            
            logger.info(f"Ответ подготовлен: success=True, user_id={user.id}, username={user.username}")
            print(f"Ответ подготовлен: success=True, user_id={user.id}, username={user.username}", flush=True)
            
            # Добавляем redirect_url если есть
            next_url = request.POST.get('next') or request.GET.get('next')
            if next_url:
                response_data['redirect_url'] = next_url
            
            # Создаем Response и устанавливаем куки сессии явно
            print(f"Создаем Response с данными: {response_data}", flush=True)
            response = Response(response_data, status=status.HTTP_200_OK)
            print("Response создан успешно", flush=True)
            
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
            error_traceback = traceback.format_exc()
            
            # Дублируем в print для гарантии что увидим
            print("=" * 80, flush=True)
            print("КРИТИЧЕСКАЯ ОШИБКА В POST TelegramAuthView", flush=True)
            print(f"Ошибка: {str(e)}", flush=True)
            print(f"Тип ошибки: {type(e).__name__}", flush=True)
            print(f"Traceback:\n{error_traceback}", flush=True)
            
            logger.error("=" * 80)
            logger.error("КРИТИЧЕСКАЯ ОШИБКА В POST TelegramAuthView")
            logger.error("=" * 80)
            logger.error(f"Ошибка: {str(e)}")
            logger.error(f"Тип ошибки: {type(e).__name__}")
            logger.error(f"Traceback:\n{error_traceback}")
            logger.error(f"Request: method={request.method}, path={request.path}")
            # Не обращаемся к request.body напрямую чтобы избежать RawPostDataException
            try:
                body_info = 'empty'
                if hasattr(request, '_body') and request._body:
                    body_info = request._body[:500].decode('utf-8', errors='ignore')
                logger.error(f"Request _body: {body_info}")
            except Exception:
                logger.error(f"Request _body: cannot read")
            
            logger.error(f"Request data: {getattr(request, 'data', 'N/A')}")
            logger.error(f"Request POST: {dict(request.POST) if request.POST else 'empty'}")
            logger.error("=" * 80)
            
            # Возвращаем более детальную ошибку в режиме отладки
            error_message = 'Внутренняя ошибка сервера при авторизации'
            if settings.DEBUG:
                error_message = f'Ошибка: {str(e)}'
            
            return Response({
                'success': False,
                'error': error_message
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
        'body': request._body.decode('utf-8', errors='ignore') if hasattr(request, '_body') and request._body else '',
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
def github_auth_redirect(request):
    """
    Генерирует URL для GitHub OAuth и делает redirect на него.
    """
    logger.info("=" * 60)
    logger.info("🚀 GITHUB OAUTH REDIRECT ЗАПРОС")
    logger.info("=" * 60)
    logger.info(f"Request method: {request.method}")
    logger.info(f"Request path: {request.path}")
    logger.info(f"Request host: {request.get_host()}")
    logger.info(f"Request GET params: {dict(request.GET)}")
    
    try:
        # Используем PUBLIC_URL из настроек для корректного redirect_uri
        # Это важно для работы за прокси и для правильной настройки в GitHub OAuth App
        public_url = getattr(settings, 'PUBLIC_URL', None)
        if not public_url:
            # Fallback: получаем из запроса
            current_domain = request.get_host()
            protocol = 'https' if request.is_secure() else 'http'
            public_url = f"{protocol}://{current_domain}"
        
        # Убираем trailing slash если есть, чтобы избежать проблем
        public_url = public_url.rstrip('/')
        
        # URL для возврата после авторизации (без trailing slash)
        redirect_uri = f"{public_url}/api/social-auth/github/callback"
        
        # Генерируем state для защиты от CSRF
        import secrets
        state = secrets.token_urlsafe(32)
        
        # Сохраняем state в сессии для проверки при callback
        request.session['github_oauth_state'] = state
        request.session.save()
        
        logger.info(f"🔍 Параметры для GitHub OAuth:")
        logger.info(f"  - public_url: {public_url}")
        logger.info(f"  - redirect_uri: {redirect_uri}")
        logger.info(f"  - state: {state}")
        logger.info(f"⚠️ ВАЖНО: Убедитесь, что этот redirect_uri настроен в GitHub OAuth App!")
        
        # Генерируем URL для GitHub OAuth
        github_oauth_url = GitHubAuthService.get_auth_url(redirect_uri, state)
        
        if not github_oauth_url:
            logger.error("Не удалось сгенерировать URL для GitHub OAuth")
            return redirect('/?open_login=true&error=Настройки GitHub не найдены')
        
        logger.info(f"🔗 Redirect на GitHub OAuth: {github_oauth_url}")
        
        return redirect(github_oauth_url)
        
    except Exception as e:
        logger.error(f"Ошибка при генерации GitHub OAuth URL: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return redirect('/?open_login=true&error=Ошибка при генерации URL авторизации')


@method_decorator(csrf_exempt, name='dispatch')
class GitHubAuthCallbackView(APIView):
    """
    View для обработки callback от GitHub OAuth.
    """
    permission_classes = [AllowAny]
    
    def get(self, request, *args, **kwargs):
        """
        Обрабатывает GET запрос с кодом авторизации от GitHub.
        """
        try:
            logger.info("=" * 60)
            logger.info("🔵 GITHUB OAUTH CALLBACK")
            logger.info("=" * 60)
            logger.info(f"Request GET params: {dict(request.GET)}")
            
            # Получаем код и state из query параметров
            code = request.GET.get('code')
            state = request.GET.get('state')
            error = request.GET.get('error')
            error_description = request.GET.get('error_description')
            
            # Проверяем наличие ошибки от GitHub
            if error:
                error_msg = error_description or error
                logger.error(f"GitHub вернул ошибку: {error}, описание: {error_msg}")
                return redirect(f'/?open_login=true&error={error_msg}')
            
            if not code:
                logger.error("Отсутствует код авторизации от GitHub")
                return redirect('/?open_login=true&error=Отсутствует код авторизации')
            
            # Проверяем state для защиты от CSRF
            session_state = request.session.get('github_oauth_state')
            if state and session_state:
                if state != session_state:
                    logger.error(f"Неверный state: ожидалось {session_state}, получено {state}")
                    return redirect('/?open_login=true&error=Неверный параметр состояния')
                # Удаляем state из сессии после проверки
                del request.session['github_oauth_state']
                request.session.save()
            
            # Получаем redirect_uri (используем тот же, что был при авторизации)
            # Используем PUBLIC_URL из настроек для консистентности
            public_url = getattr(settings, 'PUBLIC_URL', None)
            if not public_url:
                # Fallback: получаем из запроса
                current_domain = request.get_host()
                protocol = 'https' if request.is_secure() else 'http'
                public_url = f"{protocol}://{current_domain}"
            
            # Убираем trailing slash если есть
            public_url = public_url.rstrip('/')
            redirect_uri = f"{public_url}/api/social-auth/github/callback"
            
            logger.info(f"Обработка авторизации GitHub: code={code[:20]}..., redirect_uri={redirect_uri}")
            
            # Обрабатываем авторизацию
            result = GitHubAuthService.process_github_auth(code, redirect_uri, request)
            
            logger.info(f"Результат обработки авторизации GitHub: success={result.get('success') if result else False}")
            
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
            
            # Устанавливаем куки явно для обеспечения сохранения сессии
            response = redirect('/?github_auth_success=true')
            
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
            
            logger.info(f"Пользователь {user.username} успешно авторизован через GitHub, session_key={session_key}")
            
            return response
            
        except Exception as e:
            import traceback
            logger.error(f"Критическая ошибка в GitHubAuthCallbackView: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            error_message = 'Внутренняя ошибка сервера при авторизации'
            if settings.DEBUG:
                error_message = f'Ошибка: {str(e)}'
            return redirect(f'/?open_login=true&error={error_message}')


@api_view(['GET'])
@permission_classes([AllowAny])
def google_auth_redirect(request):
    """
    Генерирует URL для Google OAuth и делает redirect на него.
    """
    logger.info("=" * 60)
    logger.info("🚀 GOOGLE OAUTH REDIRECT ЗАПРОС")
    logger.info("=" * 60)
    logger.info(f"Request method: {request.method}")
    logger.info(f"Request path: {request.path}")
    logger.info(f"Request host: {request.get_host()}")
    logger.info(f"Request GET params: {dict(request.GET)}")
    
    try:
        # Используем PUBLIC_URL из настроек для корректного redirect_uri
        # Это важно для работы за прокси и для правильной настройки в Google OAuth App
        public_url = getattr(settings, 'PUBLIC_URL', None)
        if not public_url:
            # Fallback: получаем из запроса
            current_domain = request.get_host()
            protocol = 'https' if request.is_secure() else 'http'
            public_url = f"{protocol}://{current_domain}"

        # Убираем trailing slash если есть, чтобы избежать проблем
        public_url = public_url.rstrip('/')
        
        # URL для возврата после авторизации (без trailing slash)
        redirect_uri = f"{public_url}/api/social-auth/google/callback"
        
        # Генерируем state для защиты от CSRF
        import secrets
        state = secrets.token_urlsafe(32)
        
        # Сохраняем state в сессии для проверки при callback
        request.session['google_oauth_state'] = state
        request.session.save()
        
        logger.info(f"🔍 Параметры для Google OAuth:")
        logger.info(f"  - public_url: {public_url}")
        logger.info(f"  - redirect_uri: {redirect_uri}")
        logger.info(f"  - state: {state}")
        logger.info(f"⚠️ ВАЖНО: Убедитесь, что этот redirect_uri настроен в Google OAuth App!")
        
        # Генерируем URL для Google OAuth
        google_oauth_url = GoogleAuthService.get_auth_url(redirect_uri, state)
        
        if not google_oauth_url:
            logger.error("Не удалось сгенерировать URL для Google OAuth")
            return redirect('/?open_login=true&error=Настройки Google не найдены')
        
        logger.info(f"🔗 Redirect на Google OAuth: {google_oauth_url}")
        
        return redirect(google_oauth_url)
        
    except Exception as e:
        logger.error(f"Ошибка при генерации Google OAuth URL: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return redirect('/?open_login=true&error=Ошибка при генерации URL авторизации')


@method_decorator(csrf_exempt, name='dispatch')
class GoogleAuthCallbackView(APIView):
    """
    View для обработки callback от Google OAuth.
    """
    permission_classes = [AllowAny]
    
    def get(self, request, *args, **kwargs):
        """
        Обрабатывает GET запрос с кодом авторизации от Google.
        """
        try:
            logger.info("=" * 60)
            logger.info("🔵 GOOGLE OAUTH CALLBACK")
            logger.info("=" * 60)
            logger.info(f"Request GET params: {dict(request.GET)}")
            
            # Получаем код и state из query параметров
            code = request.GET.get('code')
            state = request.GET.get('state')
            error = request.GET.get('error')
            error_description = request.GET.get('error_description')
            
            # Проверяем наличие ошибки от Google
            if error:
                error_msg = error_description or error
                logger.error(f"Google вернул ошибку: {error}, описание: {error_msg}")
                return redirect(f'/?open_login=true&error={error_msg}')
            
            if not code:
                logger.error("Отсутствует код авторизации от Google")
                return redirect('/?open_login=true&error=Отсутствует код авторизации')
            
            # Проверяем state для защиты от CSRF
            session_state = request.session.get('google_oauth_state')
            if state and session_state:
                if state != session_state:
                    logger.error(f"Неверный state: ожидалось {session_state}, получено {state}")
                    return redirect('/?open_login=true&error=Неверный параметр состояния')
                # Удаляем state из сессии после проверки
                del request.session['google_oauth_state']
                request.session.save()
            
            # Получаем redirect_uri (используем тот же, что был при авторизации)
            # Используем PUBLIC_URL из настроек для консистентности
            public_url = getattr(settings, 'PUBLIC_URL', None)
            if not public_url:
                # Fallback: получаем из запроса
                current_domain = request.get_host()
                protocol = 'https' if request.is_secure() else 'http'
                public_url = f"{protocol}://{current_domain}"
            
            # Убираем trailing slash если есть
            public_url = public_url.rstrip('/')
            redirect_uri = f"{public_url}/api/social-auth/google/callback"
            
            logger.info(f"Обработка авторизации Google: code={code[:20]}..., redirect_uri={redirect_uri}")
            
            # Обрабатываем авторизацию
            result = GoogleAuthService.process_google_auth(code, redirect_uri, request)
            
            logger.info(f"Результат обработки авторизации Google: success={result.get('success') if result else False}")
            
            if not result or not result.get('success'):
                error_message = result.get('error', 'Ошибка авторизации') if result else 'Ошибка авторизации'
                return redirect(f'/?open_login=true&error={error_message}')
            
            # Авторизуем пользователя
            user = result['user']
            
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
            
            # Устанавливаем куки явно для обеспечения сохранения сессии
            response = redirect('/?google_auth_success=true')
            
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
            
            logger.info(f"Пользователь {user.username} успешно авторизован через Google, session_key={session_key}")
            
            return response
            
        except Exception as e:
            import traceback
            logger.error(f"Критическая ошибка в GoogleAuthCallbackView: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            error_message = 'Внутренняя ошибка сервера при авторизации'
            if settings.DEBUG:
                error_message = f'Ошибка: {str(e)}'
            return redirect(f'/?open_login=true&error={error_message}')


@method_decorator(csrf_exempt, name='dispatch')
class TelegramAuthCallbackView(APIView):
    """
    View для обработки callback от Telegram OAuth.
    Аналогично GitHubAuthCallbackView - принимает данные напрямую от Telegram.
    """
    permission_classes = [AllowAny]
    
    def get(self, request, *args, **kwargs):
        """
        Обрабатывает GET запрос с данными от Telegram OAuth.
        Telegram передает данные в query параметрах: ?id=...&hash=...&first_name=...
        """
        try:
            logger.info("=" * 60)
            logger.info("🔵 TELEGRAM OAUTH CALLBACK")
            logger.info("=" * 60)
            logger.info(f"Request GET params: {dict(request.GET)}")
            logger.info(f"Request path: {request.path}")
            logger.info(f"Request referer: {request.META.get('HTTP_REFERER', 'N/A')}")
            
            # Если Telegram вернул пустые query, возможно данные в hash fragment
            telegram_id = request.GET.get('id')
            telegram_hash = request.GET.get('hash')
            
            if not telegram_id and not telegram_hash:
                logger.warning("Нет query-параметров от Telegram, отдаём HTML для обработки hash fragment")
                html = """
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <title>Telegram OAuth Callback</title>
</head>
<body>
  <script>
    (function() {
      function redirectError(msg) {
        window.location.href = '/?open_login=true&error=' + encodeURIComponent(msg || 'Ошибка авторизации Telegram');
      }
      function redirectSuccess() {
        window.location.href = '/?telegram_auth_success=true';
      }
      function decodeTelegramDataFromHash() {
        const hash = window.location.hash;
        if (hash && hash.startsWith('#tgAuthResult=')) {
          try {
            const base64Data = hash.substring('#tgAuthResult='.length);
            const decoded = atob(base64Data);
            const data = JSON.parse(decoded);
            if (data.id) data.id = parseInt(data.id);
            if (data.auth_date) data.auth_date = parseInt(data.auth_date);
            return data;
          } catch (e) {
            console.error('Decode hash error', e);
            return null;
          }
        }
        return null;
      }
      function collectFromQuery() {
        const url = new URL(window.location.href);
        const id = url.searchParams.get('id');
        const hash = url.searchParams.get('hash');
        if (!id || !hash) return null;
        return {
          id: parseInt(id),
          hash: hash,
          auth_date: url.searchParams.get('auth_date') ? parseInt(url.searchParams.get('auth_date')) : null,
          first_name: url.searchParams.get('first_name') || '',
          last_name: url.searchParams.get('last_name') || '',
          username: url.searchParams.get('username') || '',
          photo_url: url.searchParams.get('photo_url') || ''
        };
      }
      const data = decodeTelegramDataFromHash() || collectFromQuery();
      if (!data || !data.id || !data.hash) {
        redirectError('Отсутствуют данные авторизации от Telegram');
        return;
      }
      fetch('/api/social-auth/telegram/auth/', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data),
        credentials: 'include'
      })
      .then(async (response) => {
        let body = null;
        try { body = await response.json(); } catch (e) {}
        if (response.ok && body && body.success) {
          redirectSuccess();
          return;
        }
        const message = (body && body.error) ? body.error : ('HTTP ' + response.status);
        redirectError(message);
      })
      .catch(() => redirectError('Ошибка сети при авторизации'));
    })();
  </script>
  <p>Авторизация через Telegram...</p>
</body>
</html>
"""
                return HttpResponse(html)
            
            # Собираем все данные от Telegram (query вариант)
            raw_data = {}
            for key, value in request.GET.items():
                if isinstance(value, list) and len(value) > 0:
                    raw_data[key] = value[0]
                elif value:
                    raw_data[key] = value
            
            logger.info(f"Собранные данные от Telegram: {raw_data}")
            
            # Преобразуем данные в правильные типы
            data = {}
            for key, value in raw_data.items():
                if isinstance(value, list):
                    val = value[0] if len(value) > 0 else ''
                else:
                    val = value
                
                if val is None or val == '':
                    if key in ['id', 'auth_date', 'hash']:
                        logger.error(f"Обязательное поле {key} пустое или отсутствует")
                        return redirect('/?open_login=true&error=Неверный формат данных')
                    continue
                
                if key == 'id':
                    data[key] = int(val)
                elif key == 'auth_date':
                    data[key] = int(val)
                else:
                    data[key] = str(val) if val else ''
            
            logger.info(f"Преобразованные данные: {data}")
            
            # Валидируем данные
            serializer = TelegramAuthSerializer(data=data)
            if not serializer.is_valid():
                logger.error(f"Ошибка валидации: {serializer.errors}")
                return redirect('/?open_login=true&error=Неверные данные авторизации')
            
            logger.info(f"Данные прошли валидацию: {serializer.validated_data}")
            
            # Обрабатываем авторизацию
            result = TelegramAuthService.process_telegram_auth(serializer.validated_data, request)
            
            logger.info(f"Результат обработки авторизации: success={result.get('success') if result else False}")
            
            if not result or not result.get('success'):
                error_message = result.get('error', 'Ошибка авторизации') if result else 'Ошибка авторизации'
                return redirect(f'/?open_login=true&error={error_message}')
            
            # Авторизуем пользователя
            user = result['user']
            
            if not user.is_active:
                logger.warning(f"Попытка авторизации неактивного пользователя: {user.username}")
                return redirect('/?open_login=true&error=Аккаунт неактивен')
            
            # Авторизуем пользователя
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            
            # Явно сохраняем сессию перед редиректом
            request.session.save()
            
            # Проверяем что сессия создана
            session_key = request.session.session_key
            logger.info(f"Сессия после login: session_key={session_key}")
            
            # Устанавливаем куки явно для обеспечения сохранения сессии
            response = redirect('/?telegram_auth_success=true')
            
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
            
            return response
            
        except Exception as e:
            import traceback
            logger.error(f"Критическая ошибка в TelegramAuthCallbackView: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            error_message = 'Внутренняя ошибка сервера при авторизации'
            if settings.DEBUG:
                error_message = f'Ошибка: {str(e)}'
            return redirect(f'/?open_login=true&error={error_message}')


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
        # ИСПРАВЛЕНИЕ: Используем отдельный callback endpoint, как для GitHub
        # Это упрощает логику и делает её более надежной
        public_url = getattr(settings, 'PUBLIC_URL', None)
        if not public_url:
            public_url = origin
        public_url = public_url.rstrip('/')
        return_to = f"{public_url}/api/social-auth/telegram/callback"
        
        logger.info(f"🔍 Параметры для Telegram OAuth:")
        logger.info(f"  - bot_username: {bot_username}")
        logger.info(f"  - bot_id: {bot_id}")
        logger.info(f"  - origin: {origin}")
        logger.info(f"  - return_to: {return_to}")
        
        # КРИТИЧНЫЙ АНАЛИЗ ПРОБЛЕМЫ TELEGRAM АВТОРИЗАЦИИ:
        #
        # 🚨 ОСНОВНАЯ ПРОБЛЕМА: Домен НЕ настроен в BotFather!
        #
        # Для работы Telegram авторизации ОБЯЗАТЕЛЬНО нужно:
        # 1. Открыть @BotFather в Telegram
        # 2. Выбрать бота @mr_proger_bot
        # 3. Выполнить команду: /setdomain
        # 4. Указать домен: quiz-code.com (БЕЗ https://)
        #
        # Без этого Telegram НЕ БУДЕТ передавать данные авторизации!
        #
        # Когда пользователь авторизуется, Telegram должен вернуть его на return_to URL
        # с данными в query параметрах: ?id=...&first_name=...&auth_date=...&hash=...
        
        # ПО АКТУАЛЬНОЙ ДОКУМЕНТАЦИИ TELEGRAM:
        # Для redirect-авторизации используем /auth/ endpoint (НЕ /embed/)
        # /embed/ предназначен для виджета в iframe, а /auth/ - для redirect в том же окне

        if bot_id:
            # Используем /auth/ endpoint для redirect-авторизации
            telegram_oauth_url = (
                f"https://oauth.telegram.org/auth?"
                f"bot_id={bot_id}&"
                f"origin={quote(origin)}&"
                f"return_to={quote(return_to.rstrip('/'))}&"
                f"request_access=write"
            )

            logger.info("=" * 100)
            logger.info("🔗 СФОРМИРОВАННЫЙ TELEGRAM AUTH URL (для redirect):")
            logger.info(f"URL: {telegram_oauth_url}")
            logger.info(f"bot_username: {bot_username}")
            logger.info(f"bot_id: {bot_id}")
            logger.info(f"origin: {origin}")
            logger.info(f"return_to: {return_to.rstrip('/')}")
            logger.info("=" * 100)

            # Проверяем настройки домена
            logger.warning("⚠️ ПРОВЕРКА НАСТРОЕК BOTFATHER:")
            logger.warning(f"  Бот: @{bot_username}")
            logger.warning(f"  Требуемый домен: {current_domain}")
            logger.warning("  В @BotFather выполните: /setdomain")
            logger.warning(f"  Укажите домен: {current_domain}")
            logger.warning("  Без этого Telegram НЕ передаст данные!")

            logger.info("✅ Используем /auth/ endpoint для redirect авторизации...")
        else:
            # Без bot_id авторизация не будет работать, возвращаем ошибку
            logger.error("❌ bot_id не получен из Telegram API, авторизация невозможна")
            return redirect('/?open_login=true&error=Ошибка настройки Telegram бота. Обратитесь к администратору.')
        
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
