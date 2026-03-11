from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from bot.database import repo
from bot.database.models import OrderStatus
from bot.services.cryptobot import CryptoBotClient
from bot.services.text_format import format_text

logger = logging.getLogger(__name__)


async def run_invoice_watcher(
    bot: Bot,
    sessionmaker: async_sessionmaker[AsyncSession],
    crypto_client: CryptoBotClient,
    interval: int,
) -> None:
    """Background task that checks unpaid crypto invoices and delivers goods after payment."""

    while True:
        try:
            async with sessionmaker() as session:
                pending_orders = await repo.list_pending_crypto_orders(session)

                invoice_ids = [order.crypto_invoice_id for order in pending_orders if order.crypto_invoice_id]
                if not invoice_ids:
                    await asyncio.sleep(interval)
                    continue

                invoices = await crypto_client.get_invoices(invoice_ids)
                invoice_map = {str(item.get("invoice_id")): item for item in invoices}

                for order in pending_orders:
                    invoice = invoice_map.get(str(order.crypto_invoice_id))
                    if not invoice:
                        continue

                    status = invoice.get("status")
                    if status == "paid":
                        await repo.mark_order_status(session, order.id, OrderStatus.paid)
                        await repo.log_event(
                            session,
                            "purchase_paid_crypto",
                            user_id=order.user_id,
                            payload={"order_id": order.id},
                        )
                        order_with_product = await repo.get_order_with_product(session, order.id)
                        if order_with_product:
                            _, product = order_with_product
                            try:
                                await bot.send_message(
                                    order.user_id,
                                    (
                                        "Оплата получена! Вот ваш товар:\n"
                                        f"{format_text(product.content)}"
                                    ),
                                    parse_mode="HTML",
                                )
                            except TelegramForbiddenError:
                                await repo.set_user_blocked(session, order.user_id, True)
                            except Exception:
                                logger.exception("Failed to send product to user %s", order.user_id)
                    elif status in {"expired", "cancelled"}:
                        await repo.mark_order_status(session, order.id, OrderStatus.expired)
        except Exception:
            logger.exception("Error in invoice watcher")

        await asyncio.sleep(interval)
