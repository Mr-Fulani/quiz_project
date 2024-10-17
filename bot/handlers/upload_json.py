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
    user_id = message.from_user.id
    username = message.from_user.username
    document = message.document

    logger.info(f"📄 Получен документ от пользователя {username} (ID: {user_id})")

    # Проверка прав доступа пользователя
    if not await is_admin(user_id, db_session):
        await message.answer("❌ У вас нет прав для выполнения этой операции.")
        logger.warning(f"⛔ Пользователь {username} (ID: {user_id}) пытался загрузить файл без прав")
        return

    logger.info(f"📦 Загружен файл: {document.file_name} (MIME: {document.mime_type})")

    # Проверяем, что файл имеет правильный тип (JSON)
    if document.mime_type == 'application/json':
        try:
            # Получаем файл через API Telegram
            file_info = await message.bot.get_file(document.file_id)
            file_path = f"{UPLOAD_DIR}/{document.file_name}"

            # Сохраняем файл на сервере
            await message.bot.download_file(file_info.file_path, file_path)
            logger.info(f"✅ Файл успешно сохранен по пути: {file_path}")

            # Начинаем процесс импорта
            logger.info(f"📥 Начало импорта задач из файла: {file_path}")
            result = await import_tasks_from_json(file_path, db_session)

            # Проверка результата импорта
            if result is None:
                await message.answer("⚠️ Произошла ошибка при обработке файла. Проверьте его формат.")
                logger.error("❗ Ошибка при импорте задач из файла.")
                return

            successfully_loaded, failed_tasks, loaded_task_ids = result

            # Лог успешного завершения
            logger.info(f"📊 Импорт завершен: {successfully_loaded} задач успешно загружены, {failed_tasks} проигнорировано.")
            logger.info(f"🆔 ID загруженных задач: {', '.join(map(str, loaded_task_ids)) if loaded_task_ids else 'нет задач'}")

            # Сообщение пользователю
            await message.answer(f"✅ Успешно загружено задач: {successfully_loaded}. Проигнорировано: {failed_tasks}.")
            if loaded_task_ids:
                await message.answer(f"🆔 ID загруженных задач: {', '.join(map(str, loaded_task_ids))}")

            logger.info("📂 Обработка загрузки задач завершена.")
        except Exception as e:
            logger.error(f"❗ Ошибка при импорте задач: {e}")
            await message.answer("⚠️ Произошла ошибка при импорте задач.")
            logger.error(traceback.format_exc())  # Вывод полного стека ошибки
    else:
        # Сообщение о неправильном формате файла
        await message.answer("❌ Пожалуйста, загрузите файл в формате JSON.")
        logger.warning(f"⚠️ Пользователь {username} (ID: {user_id}) загрузил файл неверного формата: {document.file_name}")
