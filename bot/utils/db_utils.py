# bot/utils/db_utils.py

from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Any, List
from sqlalchemy.future import select



async def fetch_one(session: AsyncSession, query) -> Optional[Any]:
    result = await session.execute(query)
    return result.scalar_one_or_none()

async def fetch_all(session: AsyncSession, query) -> List[Any]:
    result = await session.execute(query)
    return result.scalars().all()