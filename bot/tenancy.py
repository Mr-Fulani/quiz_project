"""
Мультитенантность бота: один процесс обслуживает ботов всех тенантов.

- Для каждого активного тенанта с bot_token запускается свой aiogram.Bot (main.py).
  Глобальный TELEGRAM_BOT_TOKEN, если он не совпадает ни с одним токеном тенанта,
  обслуживает тенант BOT_DEFAULT_TENANT_SLUG (или единственный тенант без своего токена).
- TenantContextMiddleware по боту, получившему апдейт, определяет тенанта и кладёт его id
  в contextvar current_tenant_id.
- Пока тенант задан, все ORM-запросы SQLAlchemy (SELECT, UPDATE, DELETE, ленивые загрузки)
  к моделям с TenantScopedMixin автоматически ограничиваются записями этого тенанта
  и «общими» записями без тенанта (tenant_id IS NULL — данные, созданные до мультитенантности;
  их можно привязать к тенанту командой Django assign_tenant_to_legacy_rows).
  Новым записям tenant_id проставляется автоматически.
- Обойти фильтр осознанно: .execution_options(skip_tenant_filter=True).

Сырой SQL (text()) фильтром не покрывается — в нём tenant_id указывайте сами.
"""

import logging
import os
from contextvars import ContextVar
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional, Tuple

from aiogram import BaseMiddleware, Bot
from sqlalchemy import event, or_, select
from sqlalchemy.orm import Session, with_loader_criteria

from bot.database.models import Tenant, TenantScopedMixin

logger = logging.getLogger(__name__)

current_tenant_id: ContextVar[Optional[int]] = ContextVar('current_tenant_id', default=None)

# telegram id бота -> id тенанта (None — бот без тенанта, работает как раньше, без фильтра)
BOT_TENANTS: Dict[int, Optional[int]] = {}


def _tenant_scoped_models() -> List[type]:
    from bot.database.database import Base
    return [mapper.class_ for mapper in Base.registry.mappers if issubclass(mapper.class_, TenantScopedMixin)]


@event.listens_for(Session, 'do_orm_execute')
def _limit_queries_to_current_tenant(orm_execute_state):
    tenant_id = current_tenant_id.get()
    if tenant_id is None or orm_execute_state.execution_options.get('skip_tenant_filter'):
        return
    if not (orm_execute_state.is_select or orm_execute_state.is_update or orm_execute_state.is_delete):
        return
    for model in _tenant_scoped_models():
        orm_execute_state.statement = orm_execute_state.statement.options(
            with_loader_criteria(
                model,
                lambda cls: or_(cls.tenant_id == tenant_id, cls.tenant_id.is_(None)),
                include_aliases=True,
            )
        )


@event.listens_for(Session, 'before_flush')
def _assign_tenant_to_new_rows(session, flush_context, instances):
    tenant_id = current_tenant_id.get()
    if tenant_id is None:
        return
    for obj in session.new:
        if isinstance(obj, TenantScopedMixin) and getattr(obj, 'tenant_id', None) is None:
            obj.tenant_id = tenant_id


def bot_id_from_token(token: str) -> int:
    return int(token.split(':', 1)[0])


def resolve_bot_tenants(
    tenants: Iterable[Tenant], global_token: Optional[str], default_slug: Optional[str] = None
) -> List[Tuple[str, Optional[int]]]:
    """
    Пары (токен бота, id тенанта) для запуска.

    Боты тенантов — по их bot_token. Глобальный токен (если он ни у кого не указан) обслуживает
    тенант default_slug, иначе единственный активный тенант без своего токена, иначе — без тенанта
    (поведение как до мультитенантности, с предупреждением в логе).
    """
    tenants = [tenant for tenant in tenants if tenant.is_active]
    pairs: Dict[str, Optional[int]] = {}
    for tenant in tenants:
        if tenant.bot_token and tenant.bot_token not in pairs:
            pairs[tenant.bot_token] = tenant.id

    if global_token and global_token not in pairs:
        default_tenant = None
        if default_slug:
            default_tenant = next((t for t in tenants if t.slug == default_slug), None)
            if default_tenant is None:
                logger.error(f"BOT_DEFAULT_TENANT_SLUG={default_slug!r}: активный тенант не найден")
        else:
            without_token = [t for t in tenants if not t.bot_token]
            if len(without_token) == 1:
                default_tenant = without_token[0]
        if default_tenant is None:
            logger.warning(
                "TELEGRAM_BOT_TOKEN не привязан к тенанту: бот работает без фильтра по тенанту. "
                "Укажите bot_token у тенанта в админке или BOT_DEFAULT_TENANT_SLUG."
            )
        pairs[global_token] = default_tenant.id if default_tenant else None

    return list(pairs.items())


async def load_bot_tenants(
    session_maker, global_token: Optional[str]
) -> Tuple[List[Tuple[str, Optional[int]]], Dict[int, Tenant]]:
    """Пары (токен, id тенанта) для запуска и тенанты по id (для настройки меню ботов)."""
    async with session_maker() as session:
        tenants = (await session.execute(select(Tenant))).scalars().all()
    pairs = resolve_bot_tenants(tenants, global_token, os.getenv('BOT_DEFAULT_TENANT_SLUG') or None)
    return pairs, {tenant.id: tenant for tenant in tenants}


def register_bot(bot: Bot, tenant_id: Optional[int]) -> None:
    BOT_TENANTS[bot.id] = tenant_id


class TenantContextMiddleware(BaseMiddleware):
    """Определяет тенанта по боту, получившему апдейт; data['tenant_id'] и contextvar current_tenant_id."""

    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any],
    ) -> Any:
        bot = data.get('bot')
        tenant_id = BOT_TENANTS.get(bot.id) if bot is not None else None
        data['tenant_id'] = tenant_id
        token = current_tenant_id.set(tenant_id)
        try:
            return await handler(event, data)
        finally:
            current_tenant_id.reset(token)
