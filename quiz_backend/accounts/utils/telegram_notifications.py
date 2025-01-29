import os

import requests





def notify_admin(action, admin, groups):
    """
    Уведомляет администратора об изменениях.
    :param action: 'added', 'updated', или 'removed'.
    :param admin: Объект администратора (TelegramAdmin).
    :param groups: Список групп/каналов (QuerySet).
    """
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not bot_token:
        print("Ошибка: TELEGRAM_BOT_TOKEN не найден в переменных окружения")
        return

    group_links = [
        f"[{group.group_name}](https://t.me/{group.username})" if group.username else f"{group.group_name} (ID: {group.group_id})"
        for group in groups
    ]

    if action == 'added':
        message = (
            f"Здравствуйте, {admin.username}!\n"
            f"Вы были добавлены в качестве администратора в следующие группы/каналы:\n"
            f"{', '.join(group_links)}"
        )
    elif action == 'updated':
        message = (
            f"Здравствуйте, {admin.username}!\n"
            f"Ваши права администратора были обновлены для следующих групп/каналов:\n"
            f"{', '.join(group_links)}"
        )
    elif action == 'removed':
        message = (
            f"Здравствуйте, {admin.username}!\n"
            f"Вы больше не являетесь администратором следующих групп/каналов:\n"
            f"{', '.join(group_links)}"
        )
    else:
        return  # Некорректное действие

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {
        'chat_id': admin.telegram_id,
        'text': message,
        'parse_mode': 'Markdown',
    }
    response = requests.post(url, data=data)
    if response.status_code == 200 and response.json().get('ok'):
        print(f"Уведомление успешно отправлено админу {admin.username}")
    else:
        print(f"Ошибка при отправке уведомления: {response.content}")



