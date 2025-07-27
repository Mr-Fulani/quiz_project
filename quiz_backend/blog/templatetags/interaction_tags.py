from django import template

register = template.Library()

@register.filter
def is_liked_by_user(obj, user):
    """Проверяет, лайкнул ли пользователь пост или проект."""
    if hasattr(obj, 'is_liked_by_user'):
        return obj.is_liked_by_user(user)
    return False

@register.filter
def is_shared_by_user(obj, user):
    """Проверяет, поделился ли пользователь постом или проектом."""
    if hasattr(obj, 'is_shared_by_user'):
        return obj.is_shared_by_user(user)
    return False

@register.filter
def get_likes_count(obj):
    """Возвращает количество лайков для поста или проекта."""
    if hasattr(obj, 'get_likes_count'):
        return obj.get_likes_count()
    return 0

@register.filter
def get_shares_count(obj):
    """Возвращает количество репостов для поста или проекта."""
    if hasattr(obj, 'get_shares_count'):
        return obj.get_shares_count()
    return 0 