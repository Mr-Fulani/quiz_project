# reply_keyboards.py

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton





def get_start_reply_keyboard() -> ReplyKeyboardMarkup:
    """
    Создает reply-клавиатуру для обычных пользователей.
    """
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🆘 Поддержка-Support")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False  # Клавиатура остаётся открытой
    )
    return keyboard




def get_admin_start_reply_keyboard() -> ReplyKeyboardMarkup:
    """
    Создает reply-клавиатуру для администраторов.
    """
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Меню Администратора")],
            [KeyboardButton(text="🆘 Поддержка-Support")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False  # Клавиатура остаётся открытой
    )
    return keyboard




def get_admin_reply_keyboard() -> ReplyKeyboardMarkup:
    """
    Создает клавиатуру с кнопками для администратора.
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Просмотреть сообщения")],
            [KeyboardButton(text="Отметить сообщение как обработанное")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )





def get_location_type_keyboard() -> ReplyKeyboardMarkup:
    """
    Создаёт клавиатуру для выбора типа локации.
    """
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="channel"), KeyboardButton(text="group")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    return keyboard



