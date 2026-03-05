from __future__ import annotations

import logging

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database import repo
from bot.handlers.catalog import send_products
from bot.handlers.menu_filters import MenuButtonFilter
from bot.keyboards.admin import admin_menu_kb
from bot.keyboards.user import (
    BTN_ADMIN_DEFAULT,
    BTN_CATALOG_DEFAULT,
    BTN_PROOFS_DEFAULT,
    BTN_SUPPORT_DEFAULT,
    main_menu_kb,
)

router = Router()
logger = logging.getLogger(__name__)


def _is_admin(user_id: int, admin_ids: list[int]) -> bool:
    return user_id in admin_ids


@router.message(MenuButtonFilter(repo.SETTING_BTN_CATALOG, BTN_CATALOG_DEFAULT))
async def menu_catalog(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    await send_products(message, session)


@router.message(MenuButtonFilter(repo.SETTING_BTN_PROOFS, BTN_PROOFS_DEFAULT))
async def menu_proofs(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    try:
        await repo.log_event(session, "proofs_view", user_id=message.from_user.id)
    except Exception:
        logger.exception("Failed to log proofs view")

    proofs_text = await repo.get_setting(
        session,
        repo.SETTING_PROOFS_TEXT,
        default="Доказательства пока не добавлены.",
    )
    labels = await repo.get_button_labels(session)
    await message.answer(
        (proofs_text or "").strip() or "Доказательства пока не добавлены.",
        reply_markup=main_menu_kb(
            _is_admin(message.from_user.id, message.bot.settings.admin_ids),
            labels=labels,
        ),
    )


@router.message(MenuButtonFilter(repo.SETTING_BTN_SUPPORT, BTN_SUPPORT_DEFAULT))
async def menu_support(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    try:
        await repo.log_event(session, "support_view", user_id=message.from_user.id)
    except Exception:
        logger.exception("Failed to log support view")

    support_contact = await repo.get_setting(session, repo.SETTING_SUPPORT_CONTACT, default="@support")
    support_contact = (support_contact or "").strip()
    if not support_contact:
        text = "Техподдержка пока не настроена."
    else:
        text = (
            "Техподдержка:\n"
            f"{support_contact}\n\n"
            "Напишите по этому контакту, чтобы получить помощь."
        )

    labels = await repo.get_button_labels(session)
    await message.answer(
        text,
        reply_markup=main_menu_kb(
            _is_admin(message.from_user.id, message.bot.settings.admin_ids),
            labels=labels,
        ),
    )


@router.message(MenuButtonFilter(repo.SETTING_BTN_ADMIN, BTN_ADMIN_DEFAULT))
async def menu_admin(message: Message, state: FSMContext) -> None:
    await state.clear()
    if not _is_admin(message.from_user.id, message.bot.settings.admin_ids):
        await message.answer(
            "Раздел доступен только администраторам.",
            reply_markup=main_menu_kb(False),
        )
        return

    await message.answer("Админ-панель:", reply_markup=admin_menu_kb())
