# bot/keyboards/quiz_keyboards.py

import logging
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Настройка локального логирования
logger = logging.getLogger(__name__)

def get_admin_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Создаёт инлайн-клавиатуру для администраторов.
    """
    builder = InlineKeyboardBuilder()

    # Добавляем кнопки админ-меню
    builder.row(
        InlineKeyboardButton(text="Создать опрос", callback_data="create_quiz")
    )
    builder.row(
        InlineKeyboardButton(text="Загрузить JSON", callback_data="upload_json"),
        InlineKeyboardButton(text="Состояние базы", callback_data="database_status")
    )
    builder.row(
        InlineKeyboardButton(text="Опубликовать по ID", callback_data="publish_by_id"),
        InlineKeyboardButton(text="Удалить по ID", callback_data="delete_task")
    )
    builder.row(
        InlineKeyboardButton(text="Опубликовать одну задачу с переводами", callback_data="publish_task_with_translations")
    )
    builder.row(
        InlineKeyboardButton(text="Топики без задач", callback_data="zero_task_topics_report"),
        InlineKeyboardButton(text="Добавить топик", callback_data="add_topic"),
        InlineKeyboardButton(text="Удалить топик", callback_data="delete_topic")
    )
    builder.row(
        InlineKeyboardButton(text="Добавить админа", callback_data="add_admin_button"),
        InlineKeyboardButton(text="Удалить админа", callback_data="remove_admin_button"),
        InlineKeyboardButton(text="Список админов", callback_data="list_admins_button")
    )
    builder.row(
        InlineKeyboardButton(text="Добавить канал", callback_data="add_channel_group_button"),
        InlineKeyboardButton(text="Удалить канал", callback_data="remove_channel_button")
    )
    builder.row(
        InlineKeyboardButton(text="Список каналов и групп", callback_data="list_channels_groups_button")
    )
    # Добавляем новые кнопки для управления вебхуками
    builder.row(
        InlineKeyboardButton(text="Добавить вебхук", callback_data="add_webhook"),
        InlineKeyboardButton(text="Удалить вебхук", callback_data="delete_webhook_menu"),
        InlineKeyboardButton(text="Список вебхуков", callback_data="list_webhooks")
    )
    # Добавляем новые кнопки для управления ссылками по умолчанию
    builder.row(
        InlineKeyboardButton(text="Добавить ссылку", callback_data="add_default_link"),
        InlineKeyboardButton(text="Удалить ссылку", callback_data="remove_default_link")
    )
    builder.row(
        InlineKeyboardButton(text="Список ссылок", callback_data="list_default_links")
    )
    # Добавляем инлайн-кнопки для управления главной статической ссылкой
    builder.row(
        InlineKeyboardButton(text="Установить главную ссылку", callback_data="set_main_fallback_link"),
        InlineKeyboardButton(text="Удалить главную ссылку", callback_data="remove_main_fallback_link")
    )
    builder.row(
        InlineKeyboardButton(text="Получить главную ссылку", callback_data="get_main_fallback_link")
    )
    # Кнопки для статистики
    builder.row(
        InlineKeyboardButton(text="📊 Моя статистика", callback_data="mystatistics"),
        InlineKeyboardButton(text="📈 Общая статистика", callback_data="allstats"),
        InlineKeyboardButton(text="📉 Статистика по ID", callback_data="userstats")
    )
    builder.row(
        InlineKeyboardButton(text="📉 Все подписчики (CSV)", callback_data="list_subscribers_all_csv"),
        InlineKeyboardButton(text="📉 Подписчики с каналов (CSV)", callback_data="list_channels_groups_subscriptions")
    )
    builder.row(
        InlineKeyboardButton(
            text="📌 Опубликовать кнопки с подпиской",
            callback_data="post_subscription_buttons"
        )
    )

    return builder.as_markup()



def get_admin_channels_keyboard(channels):
    """
    Создаёт инлайн-клавиатуру с кнопками для каждого канала.

    :param channels: Список объектов Group.
    :return: InlineKeyboardMarkup
    """
    builder = InlineKeyboardBuilder()

    # Создаём кнопки для каждого канала
    for channel in channels:
        builder.row(
            InlineKeyboardButton(
                text=f"Список подписчиков канала {channel.group_name}",
                callback_data=f"list_subscribers_csv:{channel.group_id}"
            )
        )
    return builder.as_markup()


