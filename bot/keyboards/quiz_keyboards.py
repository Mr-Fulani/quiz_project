import logging


from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, Message



# Настройка локального логирования
logger = logging.getLogger(__name__)






def get_start_reply_keyboard() -> ReplyKeyboardMarkup:
    """
    Создает reply-клавиатуру с кнопкой "Старт".
    """
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Меню")]  # Добавляем кнопку "Старт"
        ],
        resize_keyboard=True
    )
    return keyboard








def get_admin_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру для меню администратора.
    """
    builder = InlineKeyboardBuilder()

    # Добавляем кнопки, каждая кнопка будет в отдельной строке
    builder.row(
        InlineKeyboardButton(text="Создать опрос", callback_data="create_quiz")
    )
    builder.row(
        InlineKeyboardButton(text="Опубликовать опрос по ID", callback_data="publish_by_id")
    )
    builder.row(
        InlineKeyboardButton(text="Загрузить JSON", callback_data="upload_json")
    )
    builder.row(
        InlineKeyboardButton(text="Опубликовать задачу с переводами", callback_data="publish_task_with_translations")
    )
    # Добавляем кнопку для отображения состояния базы
    builder.row(
        InlineKeyboardButton(text="Состояние базы", callback_data="database_status")
    )
    # Добавим кнопку для удаления задачи по ID
    builder.row(
        InlineKeyboardButton(text="Удалить задачу по ID", callback_data="delete_task")
    )

    return builder.as_markup()









# def get_start_inline_keyboard() -> InlineKeyboardMarkup:
#     """
#     Создает инлайн-клавиатуру для старта.
#     """
#     builder = InlineKeyboardBuilder()
#
#     # Добавляем Inline-кнопку "Старт"
#     builder.row(
#         InlineKeyboardButton(
#             text="Старт",
#             callback_data="start_pressed"  # Действие при нажатии
#         )
#     )
#
#     # Возвращаем разметку
#     return builder.as_markup()





