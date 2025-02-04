from django.utils import timezone
from datetime import timedelta

class UpdateLastSeenMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            profile = request.user.profile
            # Обновляем last_seen только если прошло больше 5 минут
            if not hasattr(profile, 'last_seen') or \
               timezone.now() - profile.last_seen > timedelta(minutes=5):
                profile.last_seen = timezone.now()
                profile.save(update_fields=['last_seen'])
        return self.get_response(request) 