from django.contrib.auth.models import AnonymousUser
from .models import Profile

def user_profile(request):
    if request.user and not isinstance(request.user, AnonymousUser):
        try:
            profile = Profile.objects.get(user=request.user)
            return {
                'user_profile': profile
            }
        except Profile.DoesNotExist:
            print(f"Profile not found for user {request.user.username}")  # Для отладки
            return {}
    return {}