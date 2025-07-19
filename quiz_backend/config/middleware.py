import logging
from django.utils.deprecation import MiddlewareMixin
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from django.core.exceptions import DisallowedHost
from django.http import HttpResponseBadRequest


logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(MiddlewareMixin):
    """Middleware для логирования Telegram запросов"""
    
    def process_request(self, request):
        # Логируем только важные Telegram запросы
        if '/auth/telegram' in request.path and request.GET:
            logger.info(f"Telegram auth request: {request.method} {request.path}")
            logger.info(f"GET params: {dict(request.GET)}")
        return None


class DisableCSRFForAPI(MiddlewareMixin):
    """
    Middleware для отключения CSRF проверки для API endpoints И Telegram auth
    """
    def process_request(self, request):
        # Разрешаем любые хосты для API endpoints И Telegram auth
        if (request.path.startswith('/api/') or 
            request.path.startswith('/auth/telegram') or 
            '/telegram/' in request.path):
            # Для внутренних запросов от контейнеров устанавливаем валидный хост
            if request.META.get('HTTP_HOST') in ['quiz_backend:8000', 'quiz_backend']:
                request.META['HTTP_HOST'] = 'localhost'
                # Также устанавливаем заголовки для корректной работы с прокси
                request.META['HTTP_X_FORWARDED_HOST'] = 'localhost'
                request.META['HTTP_X_FORWARDED_PROTO'] = 'http'
        return None
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        # Отключаем CSRF для всех API endpoints И Telegram auth
        if (request.path.startswith('/api/') or 
            request.path.startswith('/auth/telegram') or 
            '/telegram/' in request.path):
            setattr(view_func, 'csrf_exempt', True)
        return None 


class AllowAllHostsMiddleware:
    """Middleware для разрешения всех хостов в разработке"""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Переопределяем get_host для разрешения всех хостов
        original_get_host = request.get_host
        
        def patched_get_host():
            try:
                return original_get_host()
            except DisallowedHost:
                # Возвращаем любой валидный хост вместо ошибки
                return 'localhost'
        
        request.get_host = patched_get_host
        response = self.get_response(request)
        return response 