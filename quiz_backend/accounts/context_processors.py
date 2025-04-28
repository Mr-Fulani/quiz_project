from django.contrib.auth.models import AnonymousUser
from .models import CustomUser

def user_profile(request):
    """
    Контекстный процессор для добавления профиля пользователя в контекст шаблона.
    """
    if request.user and not isinstance(request.user, AnonymousUser):
        return {
            'user_profile': request.user
        }
    return {}