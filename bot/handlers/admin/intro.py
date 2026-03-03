from __future__ import annotations

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database import repo
from bot.handlers.admin.filters import AdminFilter
from bot.handlers.states import AdminStates
from bot.keyboards.admin import admin_cancel_kb, admin_intro_kb

router = Router()
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())


def _normalize_text(value: str) -> str:
    return (value or "").replace("\\n", "\n")


async def _show_intro_settings(target: Message, session: AsyncSession) -> None:
    intro_text = await repo.get_setting(session, repo.SETTING_INTRO, default="")
    intro_photo = await repo.get_setting(session, repo.SETTING_INTRO_PHOTO, default="")
    intro_media_type = await repo.get_setting(session, repo.SETTING_INTRO_MEDIA_TYPE, default="none")

    has_photo = bool((intro_photo or "").strip())
    await target.answer(
        "Настройки вступительного сообщения:\n"
        f"Текст: {_normalize_text(intro_text) or '— пусто —'}\n"
        f"Медиа: {intro_media_type if has_photo else 'не установлено'}",
        reply_markup=admin_intro_kb(has_photo),
    )

    if has_photo:
        try:
            if intro_media_type == "video":
                await target.answer_video(video=intro_photo, caption="Текущее медиа вступления")
            elif intro_media_type == "animation":
                await target.answer_animation(animation=intro_photo, caption="Текущее медиа вступления")
            elif intro_media_type == "document":
                await target.answer_document(document=intro_photo, caption="Текущее медиа вступления")
            else:
                await target.answer_photo(photo=intro_photo, caption="Текущее медиа вступления")
        except TelegramBadRequest:
            await target.answer("Текущее медиа недоступно. Установите новое.")


@router.callback_query(F.data == "admin_intro")
async def admin_intro(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    await _show_intro_settings(callback.message, session)
    await callback.answer()


@router.callback_query(F.data == "admin_intro_set_text")
async def admin_intro_set_text(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminStates.set_intro)
    await callback.message.answer("Отправьте новый текст вступительного сообщения:", reply_markup=admin_cancel_kb())
    await callback.answer()


@router.message(AdminStates.set_intro)
async def admin_set_intro(message: Message, session: AsyncSession, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Отправьте текст сообщением.", reply_markup=admin_cancel_kb())
        return

    await repo.set_setting(session, repo.SETTING_INTRO, message.text)
    await state.clear()
    await message.answer("Текст вступительного сообщения обновлен.")
    await _show_intro_settings(message, session)


@router.callback_query(F.data == "admin_intro_set_photo")
async def admin_intro_set_photo(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminStates.set_intro_photo)
    await callback.message.answer("Отправьте новое фото вступительного сообщения:", reply_markup=admin_cancel_kb())
    await callback.answer()


@router.message(AdminStates.set_intro_photo, F.photo)
async def admin_set_intro_photo(message: Message, session: AsyncSession, state: FSMContext) -> None:
    photo_file_id = message.photo[-1].file_id
    await repo.set_setting(session, repo.SETTING_INTRO_PHOTO, photo_file_id)
    await repo.set_setting(session, repo.SETTING_INTRO_MEDIA_TYPE, "photo")
    await state.clear()
    await message.answer("Фото вступительного сообщения обновлено.")
    await _show_intro_settings(message, session)


@router.message(AdminStates.set_intro_photo)
async def admin_set_intro_photo_invalid(message: Message) -> None:
    await message.answer("Пожалуйста, отправьте фото.", reply_markup=admin_cancel_kb())


@router.callback_query(F.data == "admin_intro_remove_photo")
async def admin_intro_remove_photo(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    await repo.set_setting(session, repo.SETTING_INTRO_PHOTO, "")
    await repo.set_setting(session, repo.SETTING_INTRO_MEDIA_TYPE, "none")
    await callback.message.answer("Фото вступительного сообщения удалено.")
    await _show_intro_settings(callback.message, session)
    await callback.answer()
