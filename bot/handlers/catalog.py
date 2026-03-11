from __future__ import annotations

import logging
from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database import repo
from bot.keyboards.user import products_kb, product_detail_kb
from bot.services.text_format import format_text

router = Router()
logger = logging.getLogger(__name__)


async def send_products(target: Message, session: AsyncSession) -> None:
    products = await repo.list_products(session, active_only=True)
    if not products:
        await target.answer("Сейчас нет доступных товаров.")
        return
    try:
        if target.from_user:
            await repo.log_event(session, "catalog_view", user_id=target.from_user.id)
    except Exception:
        logger.exception("Failed to log catalog view")

    await target.answer("Выберите товар:", reply_markup=products_kb(products))


@router.callback_query(F.data == "back_to_products")
async def back_to_products(callback: CallbackQuery, session: AsyncSession) -> None:
    await send_products(callback.message, session)
    await callback.answer()


@router.callback_query(F.data.startswith("product:"))
async def show_product(callback: CallbackQuery, session: AsyncSession) -> None:
    product_id = int(callback.data.split(":")[1])
    product = await repo.get_product(session, product_id)
    if not product or not product.is_active:
        await callback.answer("Товар не найден", show_alert=True)
        return

    name_html = format_text(product.name or "")
    description_html = format_text(product.description or "")
    caption = (
        f"<b>{name_html}</b>\n"
        f"Цена: <b>{product.price_rub} ₽</b>\n"
        "\n"
        f"{description_html}"
    )
    try:
        await repo.log_event(
            session,
            "product_view",
            user_id=callback.from_user.id,
            payload={"product_id": product.id},
        )
    except Exception:
        logger.exception("Failed to log product view")
    labels = await repo.get_button_labels(session)
    media_type = (product.media_type or "photo").strip().lower()
    media_id = (product.photo_file_id or "").strip()

    try:
        if not media_id or media_type == "none":
            await callback.message.answer(
                caption,
                parse_mode="HTML",
                reply_markup=product_detail_kb(product.id, labels=labels),
            )
        elif media_type == "video":
            await callback.message.answer_video(
                video=media_id,
                caption=caption,
                parse_mode="HTML",
                reply_markup=product_detail_kb(product.id, labels=labels),
            )
        elif media_type == "animation":
            await callback.message.answer_animation(
                animation=media_id,
                caption=caption,
                parse_mode="HTML",
                reply_markup=product_detail_kb(product.id, labels=labels),
            )
        elif media_type == "document":
            await callback.message.answer_document(
                document=media_id,
                caption=caption,
                parse_mode="HTML",
                reply_markup=product_detail_kb(product.id, labels=labels),
            )
        else:
            await callback.message.answer_photo(
                photo=media_id,
                caption=caption,
                parse_mode="HTML",
                reply_markup=product_detail_kb(product.id, labels=labels),
            )
    except TelegramBadRequest as exc:
        if "wrong file identifier/HTTP URL specified" in str(exc).lower():
            logger.warning("Invalid product media for product_id=%s", product.id)
            await callback.message.answer(
                caption + "\n\nМедиа товара временно недоступно.",
                parse_mode="HTML",
                reply_markup=product_detail_kb(product.id, labels=labels),
            )
        else:
            raise
    await callback.answer()
