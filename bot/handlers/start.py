import logging
from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message


from bot.keyboards.quiz_keyboards import get_admin_menu_keyboard, get_start_reply_keyboard



# Настройка локального логирования
logger = logging.getLogger(__name__)


router = Router()






# Обработчик команды /start
@router.message(CommandStart())
async def start_command(message: Message):
    """
    Обработчик команды /start. Выводит приветственное сообщение и клавиатуру с кнопкой "Старт".
    """
    user_id = message.from_user.id
    username = message.from_user.username
    logger.info(f"🔔 Пользователь {username} (ID: {user_id}) отправил команду /start")

    # Отправляем сообщение с reply-клавиатурой
    await message.answer(
        "👋 Добро пожаловать! Нажмите кнопку 'Меню', чтобы продолжить.",
        reply_markup=get_start_reply_keyboard()  # Показываем клавиатуру с кнопкой "Старт"
    )





# Обработчик нажатия кнопки "Старт"
@router.message(lambda message: message.text == "Меню")
async def handle_start_button(message: Message):
    """
    Обрабатывает нажатие кнопки "Старт" и выводит admin меню с инлайн-кнопками.
    """
    await message.answer(
        "Выберите действие из меню ниже:",
        reply_markup=get_admin_menu_keyboard()  # Показываем инлайн-клавиатуру
    )













# @router.message(Command("start"))
# async def start_command(message: Message):
#     """
#     Обработчик команды /start. Выводит приветственное сообщение и клавиатуру.
#     """
#     user_id = message.from_user.id
#     username = message.from_user.username
#     logger.info(f"🔔 Пользователь {username} (ID: {user_id}) отправил команду /start")
#
#     # Отправляем сообщение с Inline-кнопкой "Старт"
#     await message.reply(
#         "👋 Добро пожаловать! Нажмите кнопку 'Старт', чтобы продолжить.",
#         reply_markup=get_admin_menu_keyboard()
#     )








# # Обработчик нажатий на Inline-кнопку "Старт"
# @router.callback_query(lambda call: call.data == "start_pressed")
# async def inline_start_pressed(call: CallbackQuery, db_session: AsyncSession):
#     """
#     Обрабатывает нажатие на кнопку 'Старт'. Проверяет, является ли пользователь администратором.
#     """
#     user_id = call.from_user.id
#     username = call.from_user.username
#
#     logger.info(f"🟢 Пользователь {username} (ID: {user_id}) нажал на кнопку 'Старт'")
#
#     # Проверяем, является ли пользователь администратором
#     if await is_admin(user_id, db_session):
#         logger.info(f"✅ Пользователь {username} (ID: {user_id}) является администратором")
#         await call.message.answer(
#             "🔑 Добро пожаловать, администратор! Теперь вам доступны следующие функции:"
#         )
#         # Здесь можно добавить дальнейший функционал для администраторов
#     else:
#         logger.info(f"🚫 Пользователь {username} (ID: {user_id}) не является администратором")
#         await call.message.answer("❌ У вас нет прав для доступа к функционалу.")
#
#     await call.answer()  # Закрываем всплывающее уведомление







