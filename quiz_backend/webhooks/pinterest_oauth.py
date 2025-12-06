"""
OAuth 2.0 flow для Pinterest API.
Позволяет получить access token с правами pins:write и boards:write.
"""
import os
import requests
import logging
from django.shortcuts import redirect
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .models import SocialMediaCredentials

logger = logging.getLogger(__name__)

# Pinterest OAuth настройки
PINTEREST_CLIENT_ID = '1538458'  # Ваш App ID
PINTEREST_CLIENT_SECRET = os.getenv('PINTEREST_CLIENT_SECRET', '')  # Из .env файла
# Определяем redirect URI в зависимости от окружения
if settings.DEBUG:
    PINTEREST_REDIRECT_URI = os.getenv('PINTEREST_REDIRECT_URI', 'http://localhost:8001/auth/pinterest/callback/')
else:
    # Для продакшена используем реальный домен
    PINTEREST_REDIRECT_URI = os.getenv('PINTEREST_REDIRECT_URI', 'https://quiz-code.com/auth/pinterest/callback/')
PINTEREST_OAUTH_BASE_URL = 'https://www.pinterest.com/oauth'
# Для Trial доступа используем Sandbox API для token exchange
_USE_SANDBOX = os.getenv('PINTEREST_USE_SANDBOX', 'true').lower() == 'true'
if _USE_SANDBOX:
    PINTEREST_API_TOKEN_URL = 'https://api-sandbox.pinterest.com/v5/oauth/token'
    logger.info("Pinterest OAuth: Используется Sandbox API для token exchange")
else:
    PINTEREST_API_TOKEN_URL = 'https://api.pinterest.com/v5/oauth/token'
    logger.info("Pinterest OAuth: Используется Production API для token exchange")


@require_http_methods(["GET"])
def pinterest_oauth_authorize(request):
    """
    Шаг 1: Перенаправляет пользователя на Pinterest для авторизации.
    
    URL: /auth/pinterest/authorize/
    """
    # Scopes для создания пинов
    scopes = [
        'boards:read',
        'boards:write',
        'pins:read',
        'pins:write',
        'user_accounts:read'
    ]
    scope_string = ','.join(scopes)
    
    # Формируем URL для авторизации
    auth_url = (
        f"{PINTEREST_OAUTH_BASE_URL}/?"
        f"client_id={PINTEREST_CLIENT_ID}&"
        f"redirect_uri={PINTEREST_REDIRECT_URI}&"
        f"response_type=code&"
        f"scope={scope_string}&"
        f"state=pinterest_auth"
    )
    
    logger.info(f"Перенаправление на Pinterest OAuth: {auth_url}")
    return redirect(auth_url)


@require_http_methods(["GET"])
@csrf_exempt
def pinterest_oauth_callback(request):
    """
    Шаг 2: Обрабатывает callback от Pinterest и обменивает code на access token.
    
    URL: /auth/pinterest/callback/
    """
    code = request.GET.get('code')
    error = request.GET.get('error')
    state = request.GET.get('state')
    
    if error:
        error_description = request.GET.get('error_description', 'Unknown error')
        logger.error(f"Pinterest OAuth error: {error} - {error_description}")
        return HttpResponse(
            f"<h1>Ошибка авторизации Pinterest</h1>"
            f"<p>Ошибка: {error}</p>"
            f"<p>Описание: {error_description}</p>"
            f"<p><a href='/admin/webhooks/socialmediacredentials/'>Вернуться в админку</a></p>",
            status=400
        )
    
    if not code:
        logger.error("Pinterest OAuth callback без code")
        return HttpResponse(
            "<h1>Ошибка: не получен authorization code</h1>"
            "<p>Попробуйте снова: <a href='/auth/pinterest/authorize/'>Авторизоваться</a></p>",
            status=400
        )
    
    # Проверяем наличие client_secret
    if not PINTEREST_CLIENT_SECRET:
        logger.error("PINTEREST_CLIENT_SECRET не установлен в .env файле")
        return HttpResponse(
            "<h1>Ошибка конфигурации</h1>"
            "<p>PINTEREST_CLIENT_SECRET не установлен в .env файле.</p>"
            "<p>Добавьте: PINTEREST_CLIENT_SECRET=ваш_секретный_ключ</p>"
            "<p><a href='/admin/webhooks/socialmediacredentials/'>Вернуться в админку</a></p>",
            status=500
        )
    
    # Обмениваем code на access token
    try:
        import base64
        
        # Pinterest API v5 может требовать Basic Authentication
        # Пробуем оба варианта: сначала с Basic Auth, потом без
        
        # Вариант 1: Basic Authentication (стандарт OAuth 2.0)
        auth_string = f"{PINTEREST_CLIENT_ID}:{PINTEREST_CLIENT_SECRET}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        
        token_data = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': PINTEREST_REDIRECT_URI,
        }
        
        logger.info(f"Обмен code на token для Pinterest")
        logger.info(f"  redirect_uri: {PINTEREST_REDIRECT_URI}")
        logger.info(f"  client_id: {PINTEREST_CLIENT_ID}")
        logger.debug(f"  client_secret установлен: {'Да' if PINTEREST_CLIENT_SECRET else 'Нет'}")
        logger.debug(f"  code: {code[:20]}...")
        logger.debug(f"  grant_type: authorization_code")
        
        # Пробуем с Basic Authentication и form-urlencoded
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': f'Basic {auth_b64}'
        }
        
        logger.debug(f"  Используем Basic Authentication")
        
        response = requests.post(
            PINTEREST_API_TOKEN_URL,
            data=token_data,
            headers=headers,
            timeout=30
        )
        
        # Если Basic Auth не сработал, пробуем альтернативный вариант
        if response.status_code == 400:
            logger.warning("Basic Auth не сработал, пробуем вариант с client_id и client_secret в теле (JSON)")
            
            # Вариант 2: JSON формат с client_id и client_secret в теле
            token_data_json = {
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': PINTEREST_REDIRECT_URI,
                'client_id': PINTEREST_CLIENT_ID,
                'client_secret': PINTEREST_CLIENT_SECRET,
            }
            
            response = requests.post(
                PINTEREST_API_TOKEN_URL,
                json=token_data_json,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
        
        if response.status_code != 200:
            error_text = response.text
            try:
                error_json = response.json()
                error_code = error_json.get('code')
                error_message = error_json.get('message', error_text)
            except:
                error_code = None
                error_message = error_text
            
            logger.error(f"Ошибка получения token: {response.status_code} - {error_message}")
            logger.error(f"  Request URL: {PINTEREST_API_TOKEN_URL}")
            logger.error(f"  Redirect URI: {PINTEREST_REDIRECT_URI}")
            logger.error(f"  Client ID: {PINTEREST_CLIENT_ID}")
            
            # Детальные инструкции для 401 ошибки
            if response.status_code == 401:
                help_text = (
                    "<h2>Возможные причины:</h2>"
                    "<ul>"
                    "<li>Неверный <code>client_secret</code> - проверьте .env файл</li>"
                    "<li>Неверный <code>redirect_uri</code> - должен точно совпадать с настройками в Pinterest Developer Portal</li>"
                    "<li>Authorization code уже использован или истек (коды одноразовые)</li>"
                    "</ul>"
                    f"<p><strong>Текущий redirect_uri:</strong> <code>{PINTEREST_REDIRECT_URI}</code></p>"
                    "<p>Убедитесь, что этот URI точно указан в Pinterest Developer Portal → Redirect URIs</p>"
                )
            else:
                help_text = ""
            
            return HttpResponse(
                f"<h1>Ошибка получения токена</h1>"
                f"<p><strong>Статус:</strong> {response.status_code}</p>"
                f"<p><strong>Ошибка:</strong> {error_message}</p>"
                f"{help_text}"
                f"<p><a href='/auth/pinterest/authorize/'>Попробовать снова</a></p>"
                f"<p><a href='/admin/webhooks/socialmediacredentials/'>Вернуться в админку</a></p>",
                status=response.status_code
            )
        
        token_response = response.json()
        access_token = token_response.get('access_token')
        refresh_token = token_response.get('refresh_token')
        expires_in = token_response.get('expires_in', 0)  # В секундах
        
        if not access_token:
            logger.error(f"Токен не получен в ответе: {token_response}")
            return HttpResponse(
                "<h1>Ошибка: токен не получен</h1>"
                "<p>Попробуйте снова: <a href='/auth/pinterest/authorize/'>Авторизоваться</a></p>",
                status=400
            )
        
        # Сохраняем токен в SocialMediaCredentials
        from django.utils import timezone
        from datetime import timedelta
        
        expires_at = None
        if expires_in:
            expires_at = timezone.now() + timedelta(seconds=expires_in)
        
        # Обновляем или создаем запись
        creds, created = SocialMediaCredentials.objects.update_or_create(
            platform='pinterest',
            defaults={
                'access_token': access_token,
                'refresh_token': refresh_token,
                'token_expires_at': expires_at,
                'is_active': True,
            }
        )
        
        logger.info(f"✅ Pinterest токен сохранен. Создан: {created}, ID: {creds.id}")
        
        # Получаем список досок сразу после получения токена
        boards_info = ""
        try:
            from tasks.services.platforms.pinterest_api import PinterestAPI
            from django.utils import timezone
            
            logger.info("Получение списка досок Pinterest после получения токена...")
            api = PinterestAPI(access_token)
            boards_data = api.get_boards()
            
            if boards_data and boards_data.get('items'):
                items = boards_data.get('items', [])
                boards_cache = {}
                for board in items:
                    board_name = board.get('name')
                    board_id = board.get('id')
                    if board_name and board_id:
                        boards_cache[board_name] = str(board_id)
                
                if boards_cache:
                    # Сохраняем доски в extra_data
                    if not creds.extra_data:
                        creds.extra_data = {}
                    creds.extra_data['boards_cache'] = boards_cache
                    creds.extra_data['boards_cache_time'] = timezone.now().isoformat()
                    creds.save(update_fields=['extra_data'])
                    
                    boards_list = ", ".join([f"{name} ({id})" for name, id in list(boards_cache.items())[:5]])
                    if len(boards_cache) > 5:
                        boards_list += f" и еще {len(boards_cache) - 5}..."
                    
                    boards_info = f"<p><strong>✅ Получено досок: {len(boards_cache)}</strong></p><p>Доски: {boards_list}</p>"
                    logger.info(f"✅ Получено и сохранено {len(boards_cache)} досок: {list(boards_cache.keys())}")
                else:
                    boards_info = "<p><strong>⚠️ Доски не найдены в ответе API</strong></p>"
                    logger.warning("Доски не найдены в ответе API")
            else:
                boards_info = "<p><strong>⚠️ Не удалось получить список досок через API</strong></p><p>Вы можете указать доски вручную в админке в поле Extra data.</p>"
                logger.warning("Не удалось получить список досок через API")
        except Exception as e:
            logger.error(f"Ошибка получения досок после получения токена: {e}", exc_info=True)
            boards_info = f"<p><strong>⚠️ Ошибка получения досок:</strong> {str(e)}</p><p>Вы можете указать доски вручную в админке в поле Extra data.</p>"
        
        # Проверяем, используется ли Sandbox API
        use_sandbox = os.getenv('PINTEREST_USE_SANDBOX', 'true').lower() == 'true'
        sandbox_note = ""
        if use_sandbox:
            sandbox_note = "<p><strong>⚠️ Важно:</strong> Используется Sandbox API. Пины будут созданы в тестовой среде и не будут видны в production Pinterest.</p>"
        
        return HttpResponse(
            f"<h1>✅ Токен успешно получен и сохранен!</h1>"
            f"<p>Токен сохранен в админке.</p>"
            f"<p>Истекает: {expires_at.strftime('%Y-%m-%d %H:%M:%S') if expires_at else 'Не указано'}</p>"
            f"{boards_info}"
            f"{sandbox_note}"
            f"<p><a href='/admin/webhooks/socialmediacredentials/{creds.id}/change/'>Открыть в админке</a></p>"
            f"<p><a href='/admin/webhooks/socialmediacredentials/'>Вернуться к списку</a></p>"
        )
        
    except Exception as e:
        logger.error(f"Ошибка обработки Pinterest OAuth callback: {e}", exc_info=True)
        return HttpResponse(
            f"<h1>Ошибка обработки</h1>"
            f"<p>Ошибка: {str(e)}</p>"
            f"<p><a href='/admin/webhooks/socialmediacredentials/'>Вернуться в админку</a></p>",
            status=500
        )

