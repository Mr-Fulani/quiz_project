"""Изоляция данных бота по тенанту (SQLite в памяти)."""
from datetime import datetime
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.database.database import Base
from bot.database.models import Tenant, TelegramAdmin, TelegramUser, Topic
from bot.tenancy import (
    BOT_TENANTS,
    TenantContextMiddleware,
    current_tenant_id,
    register_bot,
    resolve_bot_tenants,
)
from bot.services.admin_service import is_admin

TOKEN_A = '111111:AAA'
TOKEN_B = '222222:BBB'


@pytest_asyncio.fixture
async def session_maker():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        session.add_all([
            Tenant(id=1, slug='a', name='A', bot_token=TOKEN_A, is_active=True),
            Tenant(id=2, slug='b', name='B', bot_token=TOKEN_B, is_active=True),
            Topic(id=1, name='Python', tenant_id=1),
            Topic(id=2, name='Go', tenant_id=2),
            Topic(id=3, name='Legacy', tenant_id=None),
            TelegramAdmin(id=1, telegram_id=500, tenant_id=2, is_active=True),
        ])
        await session.commit()
    yield maker
    await engine.dispose()


def in_tenant(tenant_id):
    return current_tenant_id.set(tenant_id)


@pytest.mark.asyncio
async def test_select_sees_own_and_shared_rows_only(session_maker):
    token = in_tenant(1)
    try:
        async with session_maker() as session:
            names = set((await session.execute(select(Topic.name))).scalars())
            names_orm = {t.name for t in (await session.execute(select(Topic))).scalars()}
    finally:
        current_tenant_id.reset(token)
    assert names_orm == {'Python', 'Legacy'}
    assert 'Go' not in names


@pytest.mark.asyncio
async def test_update_and_delete_do_not_touch_other_tenant(session_maker):
    token = in_tenant(1)
    try:
        async with session_maker() as session:
            await session.execute(update(Topic).values(description='x'))
            await session.execute(delete(Topic).where(Topic.name == 'Go'))
            await session.commit()
    finally:
        current_tenant_id.reset(token)
    async with session_maker() as session:  # без тенанта — видно всё
        go = (await session.execute(select(Topic).where(Topic.name == 'Go'))).scalar_one()
    assert go.description is None


@pytest.mark.asyncio
async def test_new_rows_get_current_tenant(session_maker):
    token = in_tenant(2)
    try:
        async with session_maker() as session:
            session.add(TelegramUser(telegram_id=42, subscription_status='active', created_at=datetime.now()))
            await session.commit()
    finally:
        current_tenant_id.reset(token)
    async with session_maker() as session:
        user = (await session.execute(select(TelegramUser).where(TelegramUser.telegram_id == 42))).scalar_one()
    assert user.tenant_id == 2


@pytest.mark.asyncio
async def test_admin_of_other_tenant_is_not_admin(session_maker):
    token = in_tenant(1)
    try:
        async with session_maker() as session:
            assert await is_admin(500, session) is False
    finally:
        current_tenant_id.reset(token)
    token = in_tenant(2)
    try:
        async with session_maker() as session:
            assert await is_admin(500, session) is True
    finally:
        current_tenant_id.reset(token)


def test_resolve_bot_tenants():
    a = SimpleNamespace(id=1, slug='a', bot_token=TOKEN_A, is_active=True)
    b = SimpleNamespace(id=2, slug='b', bot_token=None, is_active=True)
    inactive = SimpleNamespace(id=3, slug='c', bot_token='333:CCC', is_active=False)
    # Глобальный токен достаётся единственному тенанту без своего токена
    assert dict(resolve_bot_tenants([a, b, inactive], '999:GLOBAL')) == {TOKEN_A: 1, '999:GLOBAL': 2}
    # Глобальный токен совпадает с токеном тенанта — отдельный бот не нужен
    assert dict(resolve_bot_tenants([a, b], TOKEN_A)) == {TOKEN_A: 1}
    # Явный выбор тенанта для глобального токена
    c = SimpleNamespace(id=4, slug='c', bot_token=None, is_active=True)
    assert dict(resolve_bot_tenants([a, b, c], '999:GLOBAL', default_slug='c'))['999:GLOBAL'] == 4
    # Неоднозначно — без тенанта (как раньше)
    assert dict(resolve_bot_tenants([a, b, c], '999:GLOBAL'))['999:GLOBAL'] is None


@pytest.mark.asyncio
async def test_middleware_sets_tenant_by_bot():
    bot = SimpleNamespace(id=111111)
    register_bot(bot, 1)
    seen = {}

    async def handler(event, data):
        seen['ctx'] = current_tenant_id.get()
        seen['data'] = data['tenant_id']

    await TenantContextMiddleware()(handler, object(), {'bot': bot})
    assert seen == {'ctx': 1, 'data': 1}
    assert current_tenant_id.get() is None
    BOT_TENANTS.clear()
