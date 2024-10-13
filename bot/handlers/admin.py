# import logging
# from aiogram import Router
# from aiogram.filters import Command
# from aiogram.types import Message
# from sqlalchemy.ext.asyncio import AsyncSession
#
# from bot.services.admin_service import is_admin, add_admin, remove_admin
#
#
#
# # Инициализация маршрутизатора
# router = Router()
#
#
#
# # Настройка локального логирования
# logger = logging.getLogger(__name__)
#
#
#
# @router.message(Command("add_admin"))
# async def add_admin_command(message: Message, db_session: AsyncSession):
#     try:
#         logger.info("Команда /add_admin запущена")
#         user_id = message.from_user.id
#         username = message.from_user.username
#
#         logger.info(f"Пользователь {username} ({user_id}) отправил команду add_admin")
#
#         command_params = message.text.split()
#         if len(command_params) != 3:
#             await message.reply("Неверный формат команды. Используйте /add_admin <telegram_id> <username>.")
#             return
#
#         try:
#             new_admin_id = int(command_params[1])
#             new_admin_username = command_params[2]
#         except ValueError:
#             await message.reply("ID администратора должен быть числом.")
#             return
#
#         logger.info(f"Добавляем нового администратора {new_admin_username} с ID {new_admin_id}")
#
#         # Проверяем, является ли отправитель администратором
#         if not await is_admin(user_id, db_session):
#             await message.reply("У вас нет прав для добавления администраторов.")
#             logger.warning(f"Пользователь {username} ({user_id}) пытался добавить администратора без прав.")
#             return
#
#         # Добавляем администратора
#         await add_admin(new_admin_id, new_admin_username, db_session)
#
#         await message.reply(f"Пользователь {new_admin_username} добавлен как администратор.")
#         logger.info(f"Пользователь {new_admin_username} успешно добавлен как администратор.")
#     except Exception as e:
#         logger.error(f"Ошибка при выполнении команды /add_admin: {e}")
#         await message.reply(f"Произошла ошибка: {e}")
#
#
#
# @router.message(Command("remove_admin"))
# async def remove_admin_command(message: Message, db_session: AsyncSession):
#     try:
#         logger.info("Команда /remove_admin запущена")
#         user_id = message.from_user.id
#         username = message.from_user.username
#
#         logger.info(f"Пользователь {username} ({user_id}) отправил команду remove_admin")
#
#         command_params = message.text.split()
#         if len(command_params) != 2:
#             await message.reply("Неверный формат команды. Используйте /remove_admin <telegram_id>.")
#             return
#
#         try:
#             admin_id = int(command_params[1])
#         except ValueError:
#             await message.reply("ID администратора должен быть числом.")
#             return
#
#         # Проверяем, является ли отправитель администратором
#         if not await is_admin(user_id, db_session):
#             await message.reply("У вас нет прав для удаления администраторов.")
#             logger.warning(f"Пользователь {username} ({user_id}) пытался удалить администратора без прав.")
#             return
#
#         # Удаляем администратора
#         await remove_admin(admin_id, db_session)
#
#         await message.reply(f"Пользователь с ID {admin_id} удалён из списка администраторов.")
#         logger.info(f"Пользователь с ID {admin_id} успешно удалён из списка администраторов.")
#     except Exception as e:
#         logger.error(f"Ошибка при выполнении команды /remove_admin: {e}")
#         await message.reply(f"Произошла ошибка: {e}")