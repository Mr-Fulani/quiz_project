from aiogram.types import ReplyKeyboardMarkup, KeyboardButton





def get_main_keyboard():
    """
    Создает главную клавиатуру с кнопкой /start.
    """
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    start_button = KeyboardButton(text="/start")
    keyboard.add(start_button)
    return keyboard