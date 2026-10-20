"""Бот: пост задачи без картинки — вопрос текстом (код блоком с подсветкой) и опрос."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload
from sqlalchemy import select

from bot.database.database import Base
from bot.database.models import Subtopic, Task, TaskTranslation, Tenant, Topic
from bot.services.publication_service import send_task_post
from bot.services.task_service import prepare_publication

CODE = "class Book:\n    def __str__(self):\n        return 'Book'\n\nprint(Book())"


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        s.add_all([
            Tenant(id=1, slug='code', name='Code', image_theme='code', is_active=True),
            Tenant(id=2, slug='iqro', name='Iqro', image_theme='islamic', is_active=True),
            Topic(id=1, name='Python', tenant_id=1),
            Topic(id=2, name='Fiqh', tenant_id=2),
            Subtopic(id=1, name='Oop', topic_id=1),
            Subtopic(id=2, name='Fasting', topic_id=2),
        ])
        await s.commit()
        yield s
    await engine.dispose()


async def make_task(session, tenant_id, topic_id, subtopic_id, question):
    task = Task(topic_id=topic_id, subtopic_id=subtopic_id, tenant_id=tenant_id, difficulty='easy')
    session.add(task)
    await session.flush()
    translation = TaskTranslation(task_id=task.id, language='ru', question=question,
                                  answers=['A', 'B', 'C'], correct_answer='C', explanation='Потому что C')
    session.add(translation)
    await session.commit()
    task = (await session.execute(
        select(Task).options(selectinload(Task.topic), selectinload(Task.subtopic)).where(Task.id == task.id)
    )).scalar_one()
    return task, translation


def link_service(link='https://example.com/task'):
    return SimpleNamespace(get_default_link=AsyncMock(return_value=link))


@pytest.mark.asyncio
async def test_code_post(session):
    task, translation = await make_task(session, 1, 1, 1, CODE)
    image, text, poll, button, link, _ = await prepare_publication(task, translation, session, link_service())
    assert image is None and button is None
    assert text['parse_mode'] == 'HTML'
    assert '<pre><code class="language-python">' in text['text']
    assert "return &#x27;Book&#x27;" in text['text']
    assert text['reply_markup'] is not None
    assert poll['question'] == 'Какой будет вывод?'
    assert poll['explanation'] == '💡 Потому что C'

    bot = SimpleNamespace(send_message=AsyncMock(return_value=SimpleNamespace(message_id=5)),
                          send_poll=AsyncMock(return_value=SimpleNamespace(message_id=6)))
    group = SimpleNamespace(id=9, group_id=-100)
    poll_msg = await send_task_post(bot, group, task, text, poll)
    assert poll_msg.message_id == 6
    assert task.telegram_message_ids == [5, 6] and task.message_id == 6 and task.group_id == 9


@pytest.mark.asyncio
async def test_text_post_for_islamic_tenant_without_link(session):
    task, translation = await make_task(session, 2, 2, 2, 'Какое действие нарушает пост?')
    _, text, poll, _, _, _ = await prepare_publication(task, translation, session, link_service(None))
    assert '<pre>' not in text['text'] and '📚' in text['text']
    assert text['reply_markup'] is None
    assert poll['question'] == 'Какое действие нарушает пост?'
