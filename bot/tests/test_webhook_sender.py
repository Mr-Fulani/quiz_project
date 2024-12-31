from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot.services.publication_service import publish_task_by_translation_group


@pytest.mark.asyncio
async def test_webhook_sender():
    """Тест отправки вебхука"""

    # Базовые данные
    translation_group_id = 1
    expected_image_url = "https://example.com/image.png"
    expected_language = "en"

    # Моки для бота
    message = AsyncMock()
    db_session = AsyncMock()
    bot = AsyncMock()
    msg_mock = AsyncMock(message_id=1)
    bot.send_photo.return_value = msg_mock
    bot.send_message.return_value = msg_mock
    bot.send_poll.return_value = msg_mock
    bot.get_me.return_value = MagicMock(username="test_bot")

    # Данные для БД
    translation = MagicMock(
        id=1,
        task_id=1,
        language=expected_language,
        question="Test question",
        answers=["A", "B", "C"],
        correct_answer="B",
        published=False,
        publish_date=None,
        task=None
    )

    task = MagicMock(
        id=1,
        translation_group_id=translation_group_id,
        translations=[translation],
        topic_id=1,
        published=False,
        publish_date=None
    )
    translation.task = task

    group = MagicMock(
        group_id=123456789,
        group_name="Test Group",
        topic_id=1,
        language=expected_language
    )

    # Подготовка БД
    task_result = AsyncMock()
    task_result.unique = lambda: task_result
    task_result.scalars = lambda: task_result
    task_result.all = lambda: [task]

    group_result = AsyncMock()
    group_result.scalar_one_or_none = lambda: group

    db_session.execute.side_effect = [task_result, group_result]

    # Создаем реальную клавиатуру для мока
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Learn More", url="https://real-test-url.com")]
    ])

    # Мок для prepare_publication
    async_prepare_mock = AsyncMock()
    async_prepare_mock.return_value = (
        {
            "photo": expected_image_url,
            "caption": "Test Caption"
        },
        {
            "text": "Test Text",
            "parse_mode": "MarkdownV2"
        },
        {
            "question": "Test question",
            "options": ["A", "B", "C"],
            "correct_option_id": 1,
            "explanation": "Test explanation"
        },
        {
            "text": "Дополнительная информация",
            "reply_markup": keyboard  # Передаем готовую клавиатуру
        }
    )

    with \
            patch('bot.services.task_service.prepare_publication', new=async_prepare_mock), \
            patch('bot.services.image_service.generate_image_if_needed', return_value=expected_image_url), \
            patch('requests.get', return_value=MagicMock(status_code=200, content=b"fake_image")), \
            patch('webhook_sender.send_quiz_published_webhook') as mock_webhook:
        # Выполнение функции
        result = await publish_task_by_translation_group(
            translation_group_id=translation_group_id,
            message=message,
            db_session=db_session,
            bot=bot
        )

        # Проверки
        assert result == (True, 1, 0, 1)
        assert bot.send_photo.called
        assert bot.send_message.called
        assert bot.send_poll.called
        assert mock_webhook.called
        assert db_session.commit.called