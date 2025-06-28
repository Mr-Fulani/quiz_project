from django.utils.deprecation import MiddlewareMixin
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from django.core.exceptions import DisallowedHost
from django.http import HttpResponseBadRequest


class DisableCSRFForAPI(MiddlewareMixin):
    """
    Middleware для отключения CSRF проверки для API endpoints
    И разрешения всех хостов для API запросов
    """
    def process_request(self, request):
        # Разрешаем любые хосты для API endpoints
        if request.path.startswith('/api/'):
            # Временно "обманываем" CommonMiddleware
            request.META['HTTP_HOST'] = 'localhost'
        return None
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        # Отключаем CSRF для всех API endpoints
        if request.path.startswith('/api/'):
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