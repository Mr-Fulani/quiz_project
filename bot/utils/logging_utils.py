import logging

logger = logging.getLogger(__name__)

def log_publication_start(task_id: int, translation_id: int, language: str, target: str) -> str:
    """
    Единое сообщение о начале публикации.
    """
    message = (
        f"🔄 Начинаем публикацию задачи ID `{task_id}`.\n"
        f"🌍 Публикация перевода ID `{translation_id}` на языке `{language}` в {target}."
    )
    logger.info(message)
    return message

def log_username_received(group_name: str, channel_username: str) -> str:
    message = f"✅ Username канала `{group_name}` получен: @{channel_username}"
    logger.info(message)
    return message

def log_pause(sleep_time: int, task_id: int, language: str, group_name: str) -> str:
    message = (
        f"⏸️ Пауза {sleep_time} секунд перед следующей публикацией "
        f"(Задача ID `{task_id}`, Язык: `{language}`, Канал: `{group_name}`)."
    )
    logger.info(message)
    return message

def log_webhook_sent(webhook_name: str, webhook_url: str, success: bool) -> str:
    if success:
        message = f"✅ Вебхук `{webhook_url}` ({webhook_name}) успешно отправлен."
        logger.info(message)
    else:
        message = f"❌ Вебхук `{webhook_url}` ({webhook_name}) не удалось отправить."
        logger.error(message)
    return message

def log_webhook_summary(success: int, failed: int) -> str:
    message = (
        f"📊 Итоги отправки вебхуков:\n"
        f"✅ Успешно: {success}\n"
        f"❌ Неудачно: {failed}"
    )
    logger.info(message)
    return message

def log_final_summary(published_task_ids: set, published_count: int, total_translations: int, languages: list, groups: set) -> str:
    message = (
        f"✅ Задачи с ID: {', '.join(map(str, published_task_ids))} успешно опубликованы!\n"
        f"🌍 Опубликовано переводов: {published_count} из {total_translations}\n"
        f"📜 Языки: {', '.join(sorted(languages))}\n"
        f"🏷️ Группы: {', '.join(sorted(groups))}"
    )
    logger.info(message)
    return message

def log_publication_failure(task_id: int, translation_id: int, language: str, target: str, error: Exception):
    logger.error(
        f"❌ Ошибка при публикации задачи ID {task_id}, перевод ID {translation_id} на языке '{language}' в {target}: {error}"
    )

def log_webhook_data(webhook_data: dict):
    logger.debug(f"📦 Данные для вебхука: {webhook_data}")

def log_publication_success(task_id: int, translation_id: int, language: str, target: str):
    logger.info(
        f"✅ Публикована задача с ID {task_id}, перевод ID {translation_id} на языке '{language}' в {target}."
    )