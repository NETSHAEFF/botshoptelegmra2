from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database import repo
from bot.database.models import OrderStatus
from bot.handlers.admin.filters import AdminFilter
from bot.keyboards.admin import admin_orders_kb

router = Router()
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())


@router.callback_query(F.data == "admin_orders")
async def admin_orders(callback: CallbackQuery, session: AsyncSession) -> None:
    orders = await repo.list_orders(session, limit=20)
    if not orders:
        await callback.message.answer("Заказов пока нет.")
        await callback.answer()
        return

    lines = ["Последние заказы:"]
    for order in orders:
        product = await repo.get_product(session, order.product_id)
        product_name = product.name if product else "?"
        lines.append(
            f"#{order.id} | {order.user_id} | {product_name} | {order.amount_rub} ₽ | "
            f"{order.payment_method.value} | {order.status.value}"
        )

    await callback.message.answer("\n".join(lines), reply_markup=admin_orders_kb(orders))
    await callback.answer()


@router.callback_query(F.data.startswith("admin_confirm:"))
async def admin_confirm_payment(callback: CallbackQuery, session: AsyncSession) -> None:
    order_id = int(callback.data.split(":")[1])
    order = await repo.get_order(session, order_id)
    if not order:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    if order.status == OrderStatus.paid:
        await callback.answer("Заказ уже оплачен", show_alert=True)
        return

    await repo.mark_order_status(session, order_id, OrderStatus.paid)
    await repo.log_event(
        session,
        "purchase_paid_admin",
        user_id=order.user_id,
        payload={"order_id": order_id},
    )
    order_with_product = await repo.get_order_with_product(session, order_id)
    if order_with_product:
        _, product = order_with_product
        await callback.bot.send_message(
            order.user_id,
            "Оплата подтверждена! Ваш товар:\n" + product.content,
        )

    await callback.message.answer(f"Заказ #{order_id} подтвержден.")
    await callback.answer()
