from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot.handlers.admin.filters import AdminFilter
from bot.keyboards.admin import admin_menu_kb

router = Router()
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())


@router.message(Command("admin"))
async def admin_menu(message: Message) -> None:
    await message.answer("Админ-панель:", reply_markup=admin_menu_kb())


@router.callback_query(lambda c: c.data == "admin_back")
async def admin_back(callback: CallbackQuery) -> None:
    await callback.message.answer("Админ-панель:", reply_markup=admin_menu_kb())
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin_cancel")
async def admin_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.answer("Админ-панель:", reply_markup=admin_menu_kb())
    await callback.answer()
