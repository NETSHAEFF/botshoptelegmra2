from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database import repo

logger = logging.getLogger(__name__)


async def broadcast_message(
    bot: Bot,
    session: AsyncSession,
    text: str,
    media_file_id: str | None = None,
    media_type: str | None = None,
) -> tuple[int, int]:
    """Send a message to all users. Returns (success, failed)."""

    users = await repo.list_users(session, include_blocked=False)
    success = 0
    failed = 0

    for user in users:
        try:
            if media_file_id and media_type == "photo":
                await bot.send_photo(user.id, photo=media_file_id, caption=text or None)
            elif media_file_id and media_type == "video":
                await bot.send_video(user.id, video=media_file_id, caption=text or None)
            elif media_file_id and media_type == "animation":
                await bot.send_animation(user.id, animation=media_file_id, caption=text or None)
            elif media_file_id and media_type == "document":
                await bot.send_document(user.id, document=media_file_id, caption=text or None)
            else:
                await bot.send_message(user.id, text or " ")
            success += 1
        except TelegramForbiddenError:
            failed += 1
            await repo.set_user_blocked(session, user.id, True)
        except Exception:
            failed += 1
            logger.exception("Broadcast failed for user %s", user.id)

        await asyncio.sleep(0.05)

    return success, failed
