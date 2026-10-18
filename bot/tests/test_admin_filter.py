from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.handlers import admin_menu
from bot.services.admin_service import IsAdminFilter, is_admin


def make_session(admin):
    result = MagicMock()
    result.scalars.return_value.first.return_value = admin
    session = AsyncMock()
    session.execute.return_value = result
    return session


@pytest.mark.asyncio
async def test_is_admin_true_for_active_admin():
    assert await is_admin(1, make_session(object())) is True


@pytest.mark.asyncio
async def test_is_admin_false_for_unknown_user():
    assert await is_admin(1, make_session(None)) is False


@pytest.mark.asyncio
async def test_filter_rejects_non_admin_and_events_without_user():
    event = SimpleNamespace(from_user=SimpleNamespace(id=42))
    assert await IsAdminFilter()(event, db_session=make_session(None)) is False
    assert await IsAdminFilter()(SimpleNamespace(from_user=None), db_session=make_session(object())) is False


@pytest.mark.asyncio
async def test_filter_allows_admin():
    event = SimpleNamespace(from_user=SimpleNamespace(id=42))
    assert await IsAdminFilter()(event, db_session=make_session(object())) is True


def test_admin_menu_router_is_guarded_for_messages_and_callbacks():
    for observer in (admin_menu.router.message, admin_menu.router.callback_query):
        assert any(isinstance(f.callback, IsAdminFilter) for f in observer._handler.filters or [])
