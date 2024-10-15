from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup






def get_start_inline_keyboard():
    builder = InlineKeyboardBuilder()

    # Добавляем Inline-кнопку "Старт"
    builder.button(
        text="Старт",
        callback_data="start_pressed"  # Здесь можно указать, какое событие должно произойти при нажатии
    )

    # Возвращаем разметку
    return builder.as_markup()





def get_admin_menu_keyboard():
    builder = InlineKeyboardBuilder()

    # Добавляем кнопки, каждая кнопка будет в отдельной строке
    builder.row(InlineKeyboardButton(text="Создать опрос", callback_data="create_quiz"))
    builder.row(InlineKeyboardButton(text="Опубликовать опрос по ID", callback_data="publish_by_id"))
    builder.row(InlineKeyboardButton(text="Загрузить JSON", callback_data="upload_json"))

    # Обновляем название кнопки для массовой публикации задач с переводами
    builder.row(
        InlineKeyboardButton(text="Опубликовать задачу с переводами", callback_data="publish_task_with_translations"))

    # Возвращаем разметку
    return builder.as_markup()