"""Бот: ссылки на файлы задач хранятся ключом, в коде — полный URL (как в Django)."""
import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bot import config
from bot.database.database import Base
from bot.database.models import Task, Topic
from bot.utils.storage_urls import to_public_url, to_storage_key

KEY = 'prod/tenant-a/tasks/python/images/task_1.png'


@pytest.fixture(autouse=True)
def storage_domain(monkeypatch):
    monkeypatch.setattr(config, 'USE_R2_STORAGE', True)
    monkeypatch.setattr(config, 'R2_PUBLIC_DOMAIN', 'media.example.com', raising=False)
    monkeypatch.setenv('STORAGE_LEGACY_DOMAINS', 'cdn.old.com')


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=[Topic.__table__, Task.__table__]))
    async with async_sessionmaker(engine, expire_on_commit=False)() as s:
        yield s
    await engine.dispose()


def test_conversions():
    assert to_storage_key(f'https://media.example.com/{KEY}') == KEY
    assert to_storage_key(f'https://cdn.old.com/{KEY}') == KEY
    assert to_storage_key('https://images.example.org/x.png') == 'https://images.example.org/x.png'
    assert to_public_url(KEY) == f'https://media.example.com/{KEY}'
    assert to_public_url(None) is None


@pytest.mark.asyncio
async def test_task_columns_store_key(session):
    topic = Topic(name='Python')
    session.add(topic)
    await session.flush()
    task = Task(topic_id=topic.id, difficulty='easy', image_url=f'https://media.example.com/{KEY}',
                video_urls={'ru': f'https://cdn.old.com/{KEY}'})
    session.add(task)
    await session.commit()

    raw = (await session.execute(text('SELECT image_url, video_urls FROM tasks'))).one()
    assert raw[0] == KEY
    assert KEY in raw[1] and 'cdn.old.com' not in raw[1]

    session.expunge_all()
    loaded = (await session.execute(select(Task))).scalar_one()
    assert loaded.image_url == f'https://media.example.com/{KEY}'
    assert loaded.video_urls == {'ru': f'https://media.example.com/{KEY}'}
