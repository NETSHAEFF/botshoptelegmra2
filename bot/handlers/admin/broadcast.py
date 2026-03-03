from __future__ import annotations

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.handlers.admin.filters import AdminFilter
from bot.handlers.states import AdminStates
from bot.keyboards.admin import admin_broadcast_confirm_kb, admin_cancel_kb
from bot.services.broadcaster import broadcast_message

router = Router()
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())


@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminStates.broadcast_message)
    await callback.message.answer(
        "Отправьте текст рассылки или фото с подписью.",
        reply_markup=admin_cancel_kb(),
    )
    await callback.answer()


@router.message(AdminStates.broadcast_message, F.photo)
async def broadcast_photo(message: Message, state: FSMContext) -> None:
    photo_id = message.photo[-1].file_id
    text = message.caption or ""
    await state.update_data(text=text, media_file_id=photo_id, media_type="photo")
    await message.answer("Подтвердите рассылку:", reply_markup=admin_broadcast_confirm_kb())


@router.message(AdminStates.broadcast_message)
async def broadcast_text(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Отправьте текст или фото с подписью.", reply_markup=admin_cancel_kb())
        return

    await state.update_data(text=message.text, media_file_id=None, media_type=None)
    await message.answer("Подтвердите рассылку:", reply_markup=admin_broadcast_confirm_kb())


@router.callback_query(F.data == "admin_broadcast_send")
async def broadcast_send(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    text = data.get("text")
    media_file_id = data.get("media_file_id")
    media_type = data.get("media_type")

    if not text and not media_file_id:
        await callback.message.answer("Нет данных для рассылки.")
        await state.clear()
        await callback.answer()
        return

    success, failed = await broadcast_message(
        callback.bot,
        session,
        text or "",
        media_file_id=media_file_id,
        media_type=media_type,
    )
    await state.clear()
    await callback.message.answer(f"Рассылка завершена. Успешно: {success}, Ошибки: {failed}.")
    await callback.answer()
