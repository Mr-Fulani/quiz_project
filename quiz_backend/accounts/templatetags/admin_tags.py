from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def admin_badge(user):
    """
    Отображает бейдж администратора для пользователя.
    
    Args:
        user: Объект пользователя (CustomUser)
    
    Returns:
        str: HTML код бейджа или пустая строка
    """
    if not user or not user.is_admin:
        return ""
    
    icon_name = user.admin_badge_icon
    color_class = user.admin_badge_color
    admin_type = user.admin_type
    
    if not icon_name or not color_class:
        return ""
    
    badge_html = f"""
    <span class="admin-badge {color_class}">
        <ion-icon name="{icon_name}"></ion-icon>
        {admin_type.split()[0]}
    </span>
    """
    
    return mark_safe(badge_html)


@register.simple_tag
def admin_badge_small(user):
    """
    Отображает маленький бейдж администратора (только иконка).
    
    Args:
        user: Объект пользователя (CustomUser)
    
    Returns:
        str: HTML код маленького бейджа или пустая строка
    """
    if not user or not user.is_admin:
        return ""
    
    icon_name = user.admin_badge_icon
    color_class = user.admin_badge_color
    admin_type = user.admin_type
    
    if not icon_name or not color_class:
        return ""
    
    badge_html = f"""
    <span class="admin-badge {color_class} admin-badge-small">
        <ion-icon name="{icon_name}"></ion-icon>
    </span>
    """
    
    return mark_safe(badge_html)


@register.simple_tag
def user_name_with_badge(user, show_badge=True):
    """
    Отображает имя пользователя с бейджем администратора.
    
    Args:
        user: Объект пользователя (CustomUser)
        show_badge: Показывать ли бейдж (по умолчанию True)
    
    Returns:
        str: HTML код имени с бейджем
    """
    if not user:
        return ""
    
    name_html = f'<span class="user-name">{user.username}</span>'
    
    if show_badge and user.is_admin:
        badge = admin_badge(user)
        if badge:
            name_html = f'<div class="user-name-with-badge">{name_html}{badge}</div>'
    
    return mark_safe(name_html) 