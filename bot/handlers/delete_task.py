# import logging
# 
# from aiogram import F, Router
# from aiogram.filters import StateFilter
# from aiogram.types import Message
# from sqlalchemy.ext.asyncio import AsyncSession
# 
# from bot.services.deletion_service import delete_task_by_id  # Импортируем функцию удаления
# 
# logger = logging.getLogger(__name__)
# router = Router()
# 
# 
# 
# 
# 
# @router.message(F.text.regexp(r'^\d+$'), ~StateFilter('*'))
# async def handle_delete_task(message: Message, db_session: AsyncSession):
#     """
#     Обработчик для удаления задачи по ID, если пользователь не находится ни в каком состоянии FSM.
#     """
#     task_id = int(message.text)
#     deletion_info = await delete_task_by_id(task_id, db_session)
#     if deletion_info:
#         # Формирование подробного сообщения
#         task_info = f"✅ Задачи с ID {', '.join(map(str, deletion_info['deleted_task_ids']))} успешно удалены!"
#         topic_info = f"🏷️ Топик задач: {deletion_info['topic_name'] or 'неизвестен'}"
#         translations_info = (
#             f"🌍 Удалено переводов: {deletion_info['deleted_translation_count']}\n"
#             f"📜 Языки переводов: {', '.join(deletion_info['deleted_translation_languages']) if deletion_info['deleted_translation_languages'] else 'нет переводов'}\n"
#             f"🏷️ Группы: {', '.join(deletion_info['group_names']) if deletion_info['group_names'] else 'группы не найдены'}"
#         )
# 
#         # Отправляем информацию о том, что было удалено
#         deleted_info = f"{task_info}\n{topic_info}\n{translations_info}"
#         logger.debug(f"Информация об удалении:\n{deleted_info}")
#         await message.answer(deleted_info)
#     else:
#         await message.answer(f"❌ Не удалось удалить задачу с ID {task_id}. Возможно, задача не найдена.")