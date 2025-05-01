import os

import requests
from django.db.models.signals import m2m_changed
from django.dispatch import receiver

from quiz_backend.accounts.models import TelegramAdmin, Group
from quiz_backend.accounts.utils.telegram_notifications import notify_admin


def add_admin_to_group(telegram_admin, group):
    """
    Добавляет администратора в группу/канал через Telegram Bot API.
    """
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not bot_token:
        print("Ошибка: TELEGRAM_BOT_TOKEN не найден в переменных окружения")
        return
    url = f"https://api.telegram.org/bot{bot_token}/promoteChatMember"
    data = {
        'chat_id': group.group_id,
        'user_id': telegram_admin.telegram_id,
        'can_manage_chat': True,
        'can_change_info': True,
        'can_delete_messages': True,
        'can_invite_users': True,
        'can_restrict_members': True,
        'can_pin_messages': True,
        'can_promote_members': False,
    }
    response = requests.post(url, data=data)
    if response.status_code == 200 and response.json().get('ok'):
        return True
    else:
        print(f"Ошибка при добавлении в группу {group.group_name}: {response.json()}")
        return False


def remove_admin_from_group(telegram_admin, group):
    """
    Убирает администратора из группы/канала через Telegram Bot API.
    """
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not bot_token:
        print("Ошибка: TELEGRAM_BOT_TOKEN не найден в переменных окружения")
        return
    url = f"https://api.telegram.org/bot{bot_token}/promoteChatMember"
    data = {
        'chat_id': group.group_id,
        'user_id': telegram_admin.telegram_id,
        'can_manage_chat': False,
        'can_change_info': False,
        'can_delete_messages': False,
        'can_invite_users': False,
        'can_restrict_members': False,
        'can_pin_messages': False,
        'can_promote_members': False,
    }
    response = requests.post(url, data=data)
    if response.status_code == 200 and response.json().get('ok'):
        return True
    else:
        print(f"Ошибка при удалении из группы {group.group_name}: {response.json()}")
        return False






@receiver(m2m_changed, sender=TelegramAdmin.groups.through)
def manage_admin_in_telegram(sender, instance, action, pk_set, **kwargs):
    """
    Автоматическое добавление/удаление администратора в Telegram-группы.
    """
    if action == 'post_add':  # Администратора добавили в группу
        groups = Group.objects.filter(id__in=pk_set)
        for group in groups:
            if add_admin_to_group(instance, group):
                notify_admin('added', instance, [group])

    elif action == 'post_remove':  # Администратора удалили из группы
        groups = Group.objects.filter(id__in=pk_set)
        for group in groups:
            if remove_admin_from_group(instance, group):
                notify_admin('removed', instance, [group])


