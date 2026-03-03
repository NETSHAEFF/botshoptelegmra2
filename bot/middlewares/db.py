from __future__ import annotations

from typing import Callable, Awaitable, Any

from aiogram import BaseMiddleware
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class DbSessionMiddleware(BaseMiddleware):
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def __call__(
        self,
        handler: Callable[[Any, dict], Awaitable[Any]],
        event: Any,
        data: dict,
    ) -> Any:
        async with self._sessionmaker() as session:
            data["session"] = session
            return await handler(event, data)
