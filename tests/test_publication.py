import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from bot.services.publication_service import publish_task_by_translation_group
from database.models import Task, TaskTranslation


@pytest.mark.asyncio
@patch('bot.services.publication_service.upload_to_s3')  # Мокаем загрузку в S3
@patch('bot.services.image_service.save_temp_image')  # Мокаем временное сохранение изображений
@patch('os.remove')  # Мокаем удаление файлов
async def test_publish_task_with_temp_image(mock_remove, mock_save_temp_image, mock_upload_to_s3, db_session, bot):
    # Создаем тестовую задачу с переводами
    task_translation = TaskTranslation(
        id=1,
        language="en",
        question="What is Python?",
        answers=["Language", "Animal", "Both"],
        correct_answer="Both",
        explanation="Python is both a programming language and a snake.",
        task_id=1
    )

    task = Task(
        id=1,
        translation_group_id="1234-abcd",
        published=False,
        publish_date=None,
        translations=[task_translation]
    )

    # Настраиваем корректное мокирование вызовов
    mock_scalars = AsyncMock()
    mock_scalars.return_value = [task]

    # Мокируем db_session.execute
    mock_execute = AsyncMock()
    mock_execute.scalars = AsyncMock(return_value=[task])
    db_session.execute = AsyncMock(return_value=mock_execute)

    # Мокаем успешное сохранение временного изображения
    mock_save_temp_image.return_value = '/tmp/test_image.png'

    # Мокаем успешную загрузку в S3
    mock_upload_to_s3.return_value = 'https://example.com/test_image.png'

    # Вызов функции публикации задач
    success, published_count, failed_count, total_translations = await publish_task_by_translation_group(
        translation_group_id='1234-abcd',
        message=MagicMock(),  # Мокаем сообщение для теста
        db_session=db_session,
        bot=bot
    )

    # Проверяем, что задача успешно опубликована
    assert success is True
    assert published_count == 1
    assert failed_count == 0
    assert total_translations == 1

    # Проверяем, что временное изображение было сохранено
    mock_save_temp_image.assert_called_once()

    # Проверяем, что изображение было загружено в S3
    mock_upload_to_s3.assert_called_once_with('/tmp/test_image.png', '1_en.png')

    # Проверяем, что временный файл был удален
    mock_remove.assert_called_once_with('/tmp/test_image.png')