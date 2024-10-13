import json
import logging
import os
import traceback

from aiogram import Router, F
from aiogram.types import Message, ContentType
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.admin_service import is_admin
from bot.services.task_service import import_tasks_from_json

logger = logging.getLogger(__name__)

router = Router()

# Убедимся, что папка для загрузок существует
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# Обработчик документов (включая JSON)
@router.message(F.content_type == ContentType.DOCUMENT)
async def handle_document(message: Message, db_session: AsyncSession):
    logger.info(f"Получен документ от пользователя {message.from_user.username} ({message.from_user.id})")

    if not await is_admin(message.from_user.id, db_session):
        await message.answer("У вас нет прав для выполнения этой операции.")
        logger.warning(
            f"Пользователь {message.from_user.username} ({message.from_user.id}) пытался загрузить файл без прав")
        return

    document = message.document
    logger.info(f"Загружен файл: {document.file_name}")

    if document.mime_type == 'application/json':
        # Получаем файл через API Telegram
        file_info = await message.bot.get_file(document.file_id)
        file_path = f"{UPLOAD_DIR}/{document.file_name}"

        # Сохраняем файл
        await message.bot.download_file(file_info.file_path, file_path)
        logger.info(f"Файл сохранен: {file_path}")

        # Импортируем задачи из файла
        try:
            logger.info("Получен файл, начинается процесс импорта.")
            # Импортируем задачи из файла
            result = await import_tasks_from_json(file_path, db_session)
            logger.info(f"Результат импорта задач: {result}")
            logger.info("Импорт задач завершен успешно.")


            if result is None:
                await message.answer("Произошла ошибка при обработке файла. Пожалуйста, проверьте формат.")
                logger.error("Произошла ошибка при импорте задач.")
                return

            successfully_loaded, failed_tasks = result

            # Выводим сообщение о количестве загруженных и проигнорированных задач
            await message.answer(
                    f"Задачи успешно загружены: {successfully_loaded}. Проигнорировано из-за ошибок: {failed_tasks}.")

            logger.info("Обработка загрузки задач завершена.")
        except Exception as e:
            logger.error(f"Произошла ошибка при импорте задач: {e}")
            await message.answer("Ошибка при импорте задач.")
            logger.error(traceback.format_exc())  # Вывод полного стека ошибки
    else:
        await message.answer("Пожалуйста, загрузите JSON файл.")
        logger.warning(f"Пользователь {message.from_user.username} загрузил неверный формат файла.")
