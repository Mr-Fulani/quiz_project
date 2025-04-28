from django.utils import timezone
from datetime import timedelta

class UpdateLastSeenMiddleware:
    """
    Middleware для обновления поля last_seen аутентифицированного пользователя.
    Обновляет last_seen, если прошло более 5 минут с последнего визита.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Используем request.user вместо profile
            if not hasattr(request.user, 'last_seen') or \
               timezone.now() - request.user.last_seen > timedelta(minutes=5):
                request.user.last_seen = timezone.now()
                request.user.save(update_fields=['last_seen'])
        return self.get_response(request)