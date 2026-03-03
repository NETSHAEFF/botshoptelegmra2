from __future__ import annotations

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database import repo
from bot.handlers.admin.filters import AdminFilter
from bot.handlers.states import AdminStates
from bot.keyboards.admin import admin_products_kb, admin_product_actions_kb, admin_cancel_kb

router = Router()
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())


@router.callback_query(F.data == "admin_products")
async def admin_products(callback: CallbackQuery, session: AsyncSession) -> None:
    products = await repo.list_products(session, active_only=False)
    await callback.message.answer("Товары:", reply_markup=admin_products_kb(products))
    await callback.answer()


@router.callback_query(F.data.startswith("admin_product:"))
async def admin_product_actions(callback: CallbackQuery, session: AsyncSession) -> None:
    product_id = int(callback.data.split(":")[1])
    product = await repo.get_product(session, product_id)
    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return

    text = (
        f"Товар #{product.id}\n"
        f"Название: {product.name}\n"
        f"Цена: {product.price_rub} ₽\n"
        f"Активен: {'Да' if product.is_active else 'Нет'}"
    )

    await callback.message.answer(
        text,
        reply_markup=admin_product_actions_kb(product.id, product.is_active),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_add_product")
async def admin_add_product(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminStates.add_name)
    await callback.message.answer("Введите название товара:", reply_markup=admin_cancel_kb())
    await callback.answer()


@router.message(AdminStates.add_name)
async def admin_add_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text.strip())
    await state.set_state(AdminStates.add_price)
    await message.answer("Введите цену в рублях (целое число):", reply_markup=admin_cancel_kb())


@router.message(AdminStates.add_price)
async def admin_add_price(message: Message, state: FSMContext) -> None:
    if not message.text.isdigit():
        await message.answer("Цена должна быть числом. Попробуйте снова:", reply_markup=admin_cancel_kb())
        return

    await state.update_data(price_rub=int(message.text))
    await state.set_state(AdminStates.add_description)
    await message.answer("Введите описание товара:", reply_markup=admin_cancel_kb())


@router.message(AdminStates.add_description)
async def admin_add_description(message: Message, state: FSMContext) -> None:
    await state.update_data(description=message.text)
    await state.set_state(AdminStates.add_photo)
    await message.answer("Отправьте фото товара:", reply_markup=admin_cancel_kb())


@router.message(AdminStates.add_photo, F.photo)
async def admin_add_photo(message: Message, state: FSMContext) -> None:
    await state.update_data(photo_file_id=message.photo[-1].file_id)
    await state.set_state(AdminStates.add_content)
    await message.answer("Введите контент/ссылку для доставки товара:", reply_markup=admin_cancel_kb())


@router.message(AdminStates.add_photo)
async def admin_add_photo_invalid(message: Message) -> None:
    await message.answer("Пожалуйста, отправьте фото товара.", reply_markup=admin_cancel_kb())


@router.message(AdminStates.add_content)
async def admin_add_content(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    await repo.create_product(
        session,
        name=data["name"],
        price_rub=data["price_rub"],
        description=data["description"],
        photo_file_id=data["photo_file_id"],
        media_type="photo",
        content=message.text,
    )
    await state.clear()
    await message.answer("Товар добавлен.")


@router.callback_query(F.data.startswith("admin_edit_name:"))
async def admin_edit_name(callback: CallbackQuery, state: FSMContext) -> None:
    product_id = int(callback.data.split(":")[1])
    await state.update_data(product_id=product_id)
    await state.set_state(AdminStates.edit_name)
    await callback.message.answer("Введите новое название:", reply_markup=admin_cancel_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("admin_edit_price:"))
async def admin_edit_price(callback: CallbackQuery, state: FSMContext) -> None:
    product_id = int(callback.data.split(":")[1])
    await state.update_data(product_id=product_id)
    await state.set_state(AdminStates.edit_price)
    await callback.message.answer("Введите новую цену (целое число):", reply_markup=admin_cancel_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("admin_edit_desc:"))
async def admin_edit_desc(callback: CallbackQuery, state: FSMContext) -> None:
    product_id = int(callback.data.split(":")[1])
    await state.update_data(product_id=product_id)
    await state.set_state(AdminStates.edit_description)
    await callback.message.answer("Введите новое описание:", reply_markup=admin_cancel_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("admin_edit_photo:"))
async def admin_edit_photo(callback: CallbackQuery, state: FSMContext) -> None:
    product_id = int(callback.data.split(":")[1])
    await state.update_data(product_id=product_id)
    await state.set_state(AdminStates.edit_photo)
    await callback.message.answer("Отправьте новое фото:", reply_markup=admin_cancel_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("admin_edit_content:"))
async def admin_edit_content(callback: CallbackQuery, state: FSMContext) -> None:
    product_id = int(callback.data.split(":")[1])
    await state.update_data(product_id=product_id)
    await state.set_state(AdminStates.edit_content)
    await callback.message.answer("Введите новый контент/ссылку:", reply_markup=admin_cancel_kb())
    await callback.answer()


@router.message(AdminStates.edit_name)
async def admin_save_name(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    await repo.update_product(session, data["product_id"], name=message.text.strip())
    await state.clear()
    await message.answer("Название обновлено.")


@router.message(AdminStates.edit_price)
async def admin_save_price(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not message.text.isdigit():
        await message.answer("Цена должна быть числом. Попробуйте снова:", reply_markup=admin_cancel_kb())
        return

    data = await state.get_data()
    await repo.update_product(session, data["product_id"], price_rub=int(message.text))
    await state.clear()
    await message.answer("Цена обновлена.")


@router.message(AdminStates.edit_description)
async def admin_save_description(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    await repo.update_product(session, data["product_id"], description=message.text)
    await state.clear()
    await message.answer("Описание обновлено.")


@router.message(AdminStates.edit_photo, F.photo)
async def admin_save_photo(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    await repo.update_product(session, data["product_id"], photo_file_id=message.photo[-1].file_id)
    await state.clear()
    await message.answer("Фото обновлено.")


@router.message(AdminStates.edit_photo)
async def admin_save_photo_invalid(message: Message) -> None:
    await message.answer("Пожалуйста, отправьте фото.", reply_markup=admin_cancel_kb())


@router.message(AdminStates.edit_content)
async def admin_save_content(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    await repo.update_product(session, data["product_id"], content=message.text)
    await state.clear()
    await message.answer("Контент обновлен.")


@router.callback_query(F.data.startswith("admin_toggle_active:"))
async def admin_toggle_active(callback: CallbackQuery, session: AsyncSession) -> None:
    product_id = int(callback.data.split(":")[1])
    product = await repo.get_product(session, product_id)
    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return

    await repo.update_product(session, product_id, is_active=not product.is_active)
    updated = await repo.get_product(session, product_id)
    if updated:
        await callback.message.answer(
            "Статус товара обновлен.",
            reply_markup=admin_product_actions_kb(updated.id, updated.is_active),
        )
    else:
        await callback.message.answer("Статус товара обновлен.")
    await callback.answer()


@router.callback_query(F.data.startswith("admin_delete:"))
async def admin_delete(callback: CallbackQuery) -> None:
    product_id = int(callback.data.split(":")[1])
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="Удалить", callback_data=f"admin_delete_confirm:{product_id}"),
        InlineKeyboardButton(text="Отмена", callback_data="admin_products"),
    )
    builder.adjust(1)

    await callback.message.answer("Подтвердите удаление товара:", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("admin_delete_confirm:"))
async def admin_delete_confirm(callback: CallbackQuery, session: AsyncSession) -> None:
    product_id = int(callback.data.split(":")[1])
    result = await repo.delete_product(session, product_id)
    if result == "deleted":
        await callback.message.answer("Товар удален.")
    else:
        await callback.message.answer(
            "По товару есть заказы. Товар деактивирован и скрыт из каталога."
        )
    await callback.answer()
