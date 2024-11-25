# reply_keyboards.py

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton





def get_start_reply_keyboard() -> ReplyKeyboardMarkup:
    """
    Создает reply-клавиатуру с кнопкой "Меню".
    """
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Меню")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False  # Клавиатура остаётся открытой
    )
    return keyboard



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