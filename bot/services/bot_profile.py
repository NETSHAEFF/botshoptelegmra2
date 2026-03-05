from __future__ import annotations

from aiogram import Bot


async def apply_bot_profile(
    bot: Bot,
    profile_name: str | None,
) -> None:
    name_value = (profile_name or "").strip()
    if name_value:
        await bot.set_my_name(name=name_value)
