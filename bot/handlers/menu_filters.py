from __future__ import annotations

from aiogram.filters import Filter
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database import repo


class MenuButtonFilter(Filter):
    def __init__(self, setting_key: str, default_text: str) -> None:
        self.setting_key = setting_key
        self.default_text = default_text

    async def __call__(self, message: Message, session: AsyncSession) -> bool:
        current_text = (message.text or "").strip()
        if not current_text:
            return False
        target_text = await repo.get_setting(
            session,
            self.setting_key,
            default=self.default_text,
        )
        return current_text == ((target_text or "").strip() or self.default_text)
