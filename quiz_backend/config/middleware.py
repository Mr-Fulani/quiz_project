from django.utils.deprecation import MiddlewareMixin
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse


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