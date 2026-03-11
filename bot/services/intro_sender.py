from __future__ import annotations

import logging
from typing import Any

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message

from bot.services.text_format import format_text

logger = logging.getLogger(__name__)


async def send_intro_message(
    target: Message,
    intro_text: str,
    intro_media_file_id: str | None,
    intro_media_type: str | None = "none",
    reply_markup: Any = None,
) -> None:
    """Send intro with optional media. Falls back to plain text if media is invalid."""

    media = (intro_media_file_id or "").strip()
    text = intro_text or "Добро пожаловать!"
    formatted_text = format_text(text)
    media_type = (intro_media_type or "none").strip().lower()

    if not media or media_type == "none":
        await target.answer(formatted_text, reply_markup=reply_markup, parse_mode="HTML")
        return

    try:
        caption = formatted_text if len(formatted_text) <= 1024 else None
        if media_type == "photo":
            await target.answer_photo(
                photo=media,
                caption=caption,
                parse_mode="HTML" if caption else None,
                reply_markup=reply_markup,
            )
        elif media_type == "video":
            await target.answer_video(
                video=media,
                caption=caption,
                parse_mode="HTML" if caption else None,
                reply_markup=reply_markup,
            )
        elif media_type == "animation":
            await target.answer_animation(
                animation=media,
                caption=caption,
                parse_mode="HTML" if caption else None,
                reply_markup=reply_markup,
            )
        elif media_type == "document":
            await target.answer_document(
                document=media,
                caption=caption,
                parse_mode="HTML" if caption else None,
                reply_markup=reply_markup,
            )
        else:
            await target.answer(formatted_text, reply_markup=reply_markup, parse_mode="HTML")
            return
        if caption is None:
            await target.answer(formatted_text, parse_mode="HTML")
    except TelegramBadRequest as exc:
        logger.warning("Intro media is invalid: %s", exc)
        await target.answer(formatted_text, reply_markup=reply_markup, parse_mode="HTML")
