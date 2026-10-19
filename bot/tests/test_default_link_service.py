"""Стандартная ссылка «Узнать больше» берётся из тенанта или окружения, а не из кода."""
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.database.database import Base
from bot.database.models import MainFallbackLink, Tenant
from bot.services.default_link_service import DefaultLinkService
from bot.tenancy import current_tenant_id


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        session.add_all([
            Tenant(id=1, slug='a', name='A', domain='a.example.com', is_active=True),
            Tenant(id=2, slug='b', name='B', domain='b.example.com', is_active=True),
        ])
        await session.commit()
        yield session
    await engine.dispose()


@pytest.fixture(autouse=True)
def no_env_fallback(monkeypatch):
    monkeypatch.delenv('DEFAULT_FALLBACK_LINK', raising=False)


@pytest.mark.asyncio
async def test_standard_link_is_site_of_current_bot_tenant(session):
    token = current_tenant_id.set(2)
    try:
        link = await DefaultLinkService(session).get_default_link('ru', 'Python')
    finally:
        current_tenant_id.reset(token)
    assert link == 'https://b.example.com'


@pytest.mark.asyncio
async def test_explicit_tenant_wins_over_context(session):
    assert await DefaultLinkService(session).get_default_link('ru', 'Python', tenant_id=1) == 'https://a.example.com'


@pytest.mark.asyncio
async def test_main_fallback_link_has_priority(session):
    session.add(MainFallbackLink(language='ru', link='https://t.me/channel', tenant_id=1))
    await session.commit()
    token = current_tenant_id.set(1)
    try:
        service = DefaultLinkService(session)
        assert await service.get_default_link('ru', 'Python') == 'https://t.me/channel'
        assert await service.get_main_fallback_link('en') == 'https://a.example.com'
    finally:
        current_tenant_id.reset(token)


@pytest.mark.asyncio
async def test_without_tenant_uses_env_or_nothing(session, monkeypatch):
    service = DefaultLinkService(session)
    assert await service.get_default_link('ru', 'Python') is None
    monkeypatch.setenv('DEFAULT_FALLBACK_LINK', 'https://example.org')
    assert await service.get_default_link('ru', 'Python') == 'https://example.org'
