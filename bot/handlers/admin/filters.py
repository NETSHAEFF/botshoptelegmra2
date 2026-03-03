from __future__ import annotations

from aiogram.filters import Filter
from aiogram.types import Message, CallbackQuery


class AdminFilter(Filter):
    async def __call__(self, event: Message | CallbackQuery, **kwargs) -> bool:
        bot = kwargs.get("bot")
        if bot is None or not hasattr(bot, "settings"):
            return False
        settings = bot.settings
        return event.from_user.id in settings.admin_ids
