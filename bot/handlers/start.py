from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database import repo
from bot.handlers.catalog import send_products
from bot.keyboards.user import main_menu_kb
from bot.services.intro_sender import send_intro_message

router = Router()
logger = logging.getLogger(__name__)


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession) -> None:
    await repo.upsert_user(
        session,
        tg_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
    )
    try:
        await repo.log_event(session, "start", user_id=message.from_user.id)
    except Exception:
        logger.exception("Failed to log start event")

    intro_text = await repo.get_setting(session, repo.SETTING_INTRO, default="Добро пожаловать!")
    intro_photo = await repo.get_setting(session, repo.SETTING_INTRO_PHOTO, default="")
    intro_media_type = await repo.get_setting(session, repo.SETTING_INTRO_MEDIA_TYPE, default="none")
    labels = await repo.get_button_labels(session)
    await send_intro_message(
        message,
        intro_text=intro_text,
        intro_media_file_id=intro_photo,
        intro_media_type=intro_media_type,
        reply_markup=main_menu_kb(
            message.from_user.id in message.bot.settings.admin_ids,
            labels=labels,
        ),
    )

    await send_products(message, session)
