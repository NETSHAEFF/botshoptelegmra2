from __future__ import annotations

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database import repo
from bot.handlers.admin.filters import AdminFilter
from bot.handlers.states import AdminStates
from bot.keyboards.admin import admin_payments_kb, admin_cancel_kb

router = Router()
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())


def _toggle(value: str | None) -> str:
    return "0" if value == "1" else "1"


@router.callback_query(F.data == "admin_payments")
async def admin_payments(callback: CallbackQuery, session: AsyncSession) -> None:
    crypto_enabled = await repo.get_setting(session, repo.SETTING_CRYPTO_ENABLED, default="1")
    card_enabled = await repo.get_setting(session, repo.SETTING_MANUAL_ENABLED, default="1")
    ozon_enabled = await repo.get_setting(session, repo.SETTING_OZON_ENABLED, default="0")
    yandex_enabled = await repo.get_setting(session, repo.SETTING_YANDEX_ENABLED, default="0")
    yoomoney_enabled = await repo.get_setting(session, repo.SETTING_YOOMONEY_ENABLED, default="0")

    await callback.message.answer(
        "Настройки оплаты:",
        reply_markup=admin_payments_kb(
            crypto_enabled == "1",
            card_enabled == "1",
            ozon_enabled == "1",
            yandex_enabled == "1",
            yoomoney_enabled == "1",
        ),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_toggle_crypto")
async def admin_toggle_crypto(callback: CallbackQuery, session: AsyncSession) -> None:
    current = await repo.get_setting(session, repo.SETTING_CRYPTO_ENABLED, default="1")
    await repo.set_setting(session, repo.SETTING_CRYPTO_ENABLED, _toggle(current))
    await admin_payments(callback, session)


@router.callback_query(F.data == "admin_toggle_card")
async def admin_toggle_card(callback: CallbackQuery, session: AsyncSession) -> None:
    current = await repo.get_setting(session, repo.SETTING_MANUAL_ENABLED, default="1")
    await repo.set_setting(session, repo.SETTING_MANUAL_ENABLED, _toggle(current))
    await admin_payments(callback, session)


@router.callback_query(F.data == "admin_toggle_ozon")
async def admin_toggle_ozon(callback: CallbackQuery, session: AsyncSession) -> None:
    current = await repo.get_setting(session, repo.SETTING_OZON_ENABLED, default="0")
    await repo.set_setting(session, repo.SETTING_OZON_ENABLED, _toggle(current))
    await admin_payments(callback, session)


@router.callback_query(F.data == "admin_toggle_yandex")
async def admin_toggle_yandex(callback: CallbackQuery, session: AsyncSession) -> None:
    current = await repo.get_setting(session, repo.SETTING_YANDEX_ENABLED, default="0")
    await repo.set_setting(session, repo.SETTING_YANDEX_ENABLED, _toggle(current))
    await admin_payments(callback, session)


@router.callback_query(F.data == "admin_toggle_yoomoney")
async def admin_toggle_yoomoney(callback: CallbackQuery, session: AsyncSession) -> None:
    current = await repo.get_setting(session, repo.SETTING_YOOMONEY_ENABLED, default="0")
    await repo.set_setting(session, repo.SETTING_YOOMONEY_ENABLED, _toggle(current))
    await admin_payments(callback, session)


@router.callback_query(F.data == "admin_edit_card_instructions")
async def admin_edit_card_instructions(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminStates.set_manual_instructions)
    await callback.message.answer("Отправьте реквизиты для Перевод/Карта:", reply_markup=admin_cancel_kb())
    await callback.answer()


@router.message(AdminStates.set_manual_instructions)
async def admin_save_card_instructions(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await repo.set_setting(session, repo.SETTING_MANUAL_INSTRUCTIONS, message.text)
    await state.clear()
    await message.answer("Реквизиты Перевод/Карта обновлены.")


@router.callback_query(F.data == "admin_edit_ozon_instructions")
async def admin_edit_ozon_instructions(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminStates.set_ozon_instructions)
    await callback.message.answer("Отправьте реквизиты для Озон Банк:", reply_markup=admin_cancel_kb())
    await callback.answer()


@router.message(AdminStates.set_ozon_instructions)
async def admin_save_ozon_instructions(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await repo.set_setting(session, repo.SETTING_OZON_INSTRUCTIONS, message.text)
    await state.clear()
    await message.answer("Реквизиты Озон Банк обновлены.")


@router.callback_query(F.data == "admin_edit_yandex_instructions")
async def admin_edit_yandex_instructions(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminStates.set_yandex_instructions)
    await callback.message.answer("Отправьте реквизиты для Яндекс Банк:", reply_markup=admin_cancel_kb())
    await callback.answer()


@router.message(AdminStates.set_yandex_instructions)
async def admin_save_yandex_instructions(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await repo.set_setting(session, repo.SETTING_YANDEX_INSTRUCTIONS, message.text)
    await state.clear()
    await message.answer("Реквизиты Яндекс Банк обновлены.")


@router.callback_query(F.data == "admin_edit_yoomoney_instructions")
async def admin_edit_yoomoney_instructions(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminStates.set_yoomoney_instructions)
    await callback.message.answer("Отправьте реквизиты для ЮMoney:", reply_markup=admin_cancel_kb())
    await callback.answer()


@router.message(AdminStates.set_yoomoney_instructions)
async def admin_save_yoomoney_instructions(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await repo.set_setting(session, repo.SETTING_YOOMONEY_INSTRUCTIONS, message.text)
    await state.clear()
    await message.answer("Реквизиты ЮMoney обновлены.")
