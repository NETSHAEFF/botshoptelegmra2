from __future__ import annotations

import logging

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database import repo
from bot.database.models import OrderStatus, PaymentMethod
from bot.handlers.states import UserStates
from bot.keyboards.user import (
    payment_methods_kb,
    crypto_invoice_kb,
    manual_payment_kb,
)
from bot.keyboards.admin import admin_confirm_order_kb
from bot.services.cryptobot import CryptoBotError
from bot.services.text_format import format_text

logger = logging.getLogger(__name__)

router = Router()
MANUAL_METHODS = {
    PaymentMethod.manual,
    PaymentMethod.manual_card,
    PaymentMethod.manual_ozon,
    PaymentMethod.manual_yandex,
    PaymentMethod.manual_yoomoney,
}


def _is_enabled(value: str | None) -> bool:
    return value == "1"


def _normalize_text(value: str) -> str:
    # Support \n stored in DB / env files
    return value.replace("\\n", "\n")


async def _safe_log_event(
    session: AsyncSession,
    event_type: str,
    user_id: int | None = None,
    payload: dict | None = None,
) -> None:
    try:
        await repo.log_event(session, event_type, user_id=user_id, payload=payload)
    except Exception:
        logger.exception("Failed to log event: %s", event_type)


async def _get_payment_flags(session: AsyncSession) -> tuple[bool, bool, bool, bool, bool]:
    crypto_enabled = _is_enabled(
        await repo.get_setting(session, repo.SETTING_CRYPTO_ENABLED, default="1")
    )
    card_enabled = _is_enabled(
        await repo.get_setting(session, repo.SETTING_MANUAL_ENABLED, default="1")
    )
    ozon_enabled = _is_enabled(
        await repo.get_setting(session, repo.SETTING_OZON_ENABLED, default="0")
    )
    yandex_enabled = _is_enabled(
        await repo.get_setting(session, repo.SETTING_YANDEX_ENABLED, default="0")
    )
    yoomoney_enabled = _is_enabled(
        await repo.get_setting(session, repo.SETTING_YOOMONEY_ENABLED, default="0")
    )
    return crypto_enabled, card_enabled, ozon_enabled, yandex_enabled, yoomoney_enabled


async def _start_crypto_payment(
    callback: CallbackQuery,
    session: AsyncSession,
    product_id: int,
) -> None:
    product = await repo.get_product(session, product_id)
    if not product or not product.is_active:
        await callback.answer("Товар не найден", show_alert=True)
        return
    await _safe_log_event(
        session,
        "payment_start_crypto",
        user_id=callback.from_user.id,
        payload={"product_id": product.id},
    )

    order = await repo.create_order(
        session,
        user_id=callback.from_user.id,
        product_id=product.id,
        amount_rub=product.price_rub,
        payment_method=PaymentMethod.crypto,
        status=OrderStatus.pending,
    )

    settings = callback.bot.settings
    crypto_client = callback.bot.cryptobot

    try:
        invoice = await crypto_client.create_invoice(
            amount=product.price_rub,
            fiat_currency=settings.crypto_fiat_currency,
            description=product.name,
            payload=str(order.id),
        )
    except CryptoBotError:
        logger.exception("Failed to create CryptoBot invoice")
        await repo.mark_order_status(session, order.id, OrderStatus.cancelled)
        await callback.message.answer("Не удалось создать инвойс. Попробуйте позже.")
        return

    invoice_id = str(invoice.get("invoice_id"))
    pay_url = invoice.get("bot_invoice_url")

    if not invoice_id or not pay_url:
        await repo.mark_order_status(session, order.id, OrderStatus.cancelled)
        await callback.message.answer("Ошибка создания инвойса. Попробуйте позже.")
        return

    await repo.set_order_invoice(session, order.id, invoice_id, pay_url)
    labels = await repo.get_button_labels(session)

    await callback.message.answer(
        "Счет создан. Оплатите по кнопке ниже.",
        reply_markup=crypto_invoice_kb(order.id, pay_url, labels=labels),
    )
    await callback.answer()


async def _start_manual_payment(
    callback: CallbackQuery,
    session: AsyncSession,
    product_id: int,
    *,
    setting_instructions_key: str,
    payment_method: PaymentMethod,
    event_type: str,
) -> None:
    product = await repo.get_product(session, product_id)
    if not product or not product.is_active:
        await callback.answer("Товар не найден", show_alert=True)
        return
    await _safe_log_event(
        session,
        event_type,
        user_id=callback.from_user.id,
        payload={"product_id": product.id},
    )

    order = await repo.create_order(
        session,
        user_id=callback.from_user.id,
        product_id=product.id,
        amount_rub=product.price_rub,
        payment_method=payment_method,
        status=OrderStatus.waiting_receipt,
    )

    instructions = await repo.get_setting(
        session,
        setting_instructions_key,
        default="Оплата вручную недоступна.",
    )
    labels = await repo.get_button_labels(session)

    await callback.message.answer(
        format_text(_normalize_text(instructions)),
        parse_mode="HTML",
        reply_markup=manual_payment_kb(order.id, labels=labels),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("buy:"))
async def choose_payment_method(callback: CallbackQuery, session: AsyncSession) -> None:
    product_id = int(callback.data.split(":")[1])
    await _safe_log_event(
        session,
        "payment_menu_open",
        user_id=callback.from_user.id,
        payload={"product_id": product_id},
    )

    crypto_enabled, card_enabled, ozon_enabled, yandex_enabled, yoomoney_enabled = await _get_payment_flags(session)

    if not crypto_enabled and not card_enabled and not ozon_enabled and not yandex_enabled and not yoomoney_enabled:
        await callback.message.answer("Сейчас прием оплат отключен.")
        await callback.answer()
        return

    enabled_methods = [crypto_enabled, card_enabled, ozon_enabled, yandex_enabled, yoomoney_enabled]
    if enabled_methods.count(True) > 1:
        labels = await repo.get_button_labels(session)
        await callback.message.answer(
            "Выберите способ оплаты:",
            reply_markup=payment_methods_kb(
                product_id,
                crypto_enabled,
                card_enabled,
                ozon_enabled,
                yandex_enabled,
                yoomoney_enabled,
                labels=labels,
            ),
        )
        await callback.answer()
        return

    if crypto_enabled:
        await _start_crypto_payment(callback, session, product_id)
    elif card_enabled:
        await _start_manual_payment(
            callback,
            session,
            product_id,
            setting_instructions_key=repo.SETTING_MANUAL_INSTRUCTIONS,
            payment_method=PaymentMethod.manual_card,
            event_type="payment_start_manual_card",
        )
    elif ozon_enabled:
        await _start_manual_payment(
            callback,
            session,
            product_id,
            setting_instructions_key=repo.SETTING_OZON_INSTRUCTIONS,
            payment_method=PaymentMethod.manual_ozon,
            event_type="payment_start_manual_ozon",
        )
    elif yandex_enabled:
        await _start_manual_payment(
            callback,
            session,
            product_id,
            setting_instructions_key=repo.SETTING_YANDEX_INSTRUCTIONS,
            payment_method=PaymentMethod.manual_yandex,
            event_type="payment_start_manual_yandex",
        )
    else:
        await _start_manual_payment(
            callback,
            session,
            product_id,
            setting_instructions_key=repo.SETTING_YOOMONEY_INSTRUCTIONS,
            payment_method=PaymentMethod.manual_yoomoney,
            event_type="payment_start_manual_yoomoney",
        )


@router.callback_query(F.data.startswith("pay_crypto:"))
async def pay_crypto(callback: CallbackQuery, session: AsyncSession) -> None:
    product_id = int(callback.data.split(":")[1])
    await _start_crypto_payment(callback, session, product_id)


@router.callback_query(F.data.startswith("pay_card:"))
async def pay_card(callback: CallbackQuery, session: AsyncSession) -> None:
    product_id = int(callback.data.split(":")[1])
    await _start_manual_payment(
        callback,
        session,
        product_id,
        setting_instructions_key=repo.SETTING_MANUAL_INSTRUCTIONS,
        payment_method=PaymentMethod.manual_card,
        event_type="payment_start_manual_card",
    )


@router.callback_query(F.data.startswith("pay_ozon:"))
async def pay_ozon(callback: CallbackQuery, session: AsyncSession) -> None:
    product_id = int(callback.data.split(":")[1])
    await _start_manual_payment(
        callback,
        session,
        product_id,
        setting_instructions_key=repo.SETTING_OZON_INSTRUCTIONS,
        payment_method=PaymentMethod.manual_ozon,
        event_type="payment_start_manual_ozon",
    )


@router.callback_query(F.data.startswith("pay_yandex:"))
async def pay_yandex(callback: CallbackQuery, session: AsyncSession) -> None:
    product_id = int(callback.data.split(":")[1])
    await _start_manual_payment(
        callback,
        session,
        product_id,
        setting_instructions_key=repo.SETTING_YANDEX_INSTRUCTIONS,
        payment_method=PaymentMethod.manual_yandex,
        event_type="payment_start_manual_yandex",
    )


@router.callback_query(F.data.startswith("pay_yoomoney:"))
async def pay_yoomoney(callback: CallbackQuery, session: AsyncSession) -> None:
    product_id = int(callback.data.split(":")[1])
    await _start_manual_payment(
        callback,
        session,
        product_id,
        setting_instructions_key=repo.SETTING_YOOMONEY_INSTRUCTIONS,
        payment_method=PaymentMethod.manual_yoomoney,
        event_type="payment_start_manual_yoomoney",
    )


@router.callback_query(F.data.startswith("check_crypto:"))
async def check_crypto_payment(callback: CallbackQuery, session: AsyncSession) -> None:
    order_id = int(callback.data.split(":")[1])
    order = await repo.get_order(session, order_id)
    if not order or order.user_id != callback.from_user.id:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    if not order.crypto_invoice_id:
        await callback.answer("Инвойс не найден", show_alert=True)
        return

    if order.status == OrderStatus.paid:
        await callback.answer("Заказ уже оплачен", show_alert=True)
        return

    crypto_client = callback.bot.cryptobot
    invoices = await crypto_client.get_invoices([str(order.crypto_invoice_id)])
    if not invoices:
        await callback.answer("Инвойс не найден", show_alert=True)
        return

    status = invoices[0].get("status")
    if status == "paid":
        await repo.mark_order_status(session, order.id, OrderStatus.paid)
        await _safe_log_event(
            session,
            "purchase_paid_crypto",
            user_id=callback.from_user.id,
            payload={"order_id": order.id},
        )
        order_with_product = await repo.get_order_with_product(session, order.id)
        if order_with_product:
            _, product = order_with_product
            await callback.message.answer(
                "Оплата подтверждена! Ваш товар:\n" + format_text(product.content),
                parse_mode="HTML",
            )
    else:
        await callback.answer("Оплата еще не получена", show_alert=True)


@router.callback_query(F.data.startswith("manual_paid:"))
async def manual_paid(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    order_id = int(callback.data.split(":")[1])
    order = await repo.get_order(session, order_id)
    if not order or order.user_id != callback.from_user.id:
        await callback.answer("Заказ не найден", show_alert=True)
        return
    if order.payment_method not in MANUAL_METHODS:
        await callback.answer("Для этого заказа чек не требуется.", show_alert=True)
        return

    # Switch user into receipt upload state
    await state.set_state(UserStates.waiting_receipt)
    await state.update_data(order_id=order_id)
    await callback.message.answer("Пожалуйста, пришлите чек (фото или файл).")
    await callback.answer()


@router.message(UserStates.waiting_receipt, F.photo)
async def receive_receipt_photo(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    order_id = data.get("order_id")
    if not order_id:
        await message.answer("Заказ не найден.")
        await state.clear()
        return

    file_id = message.photo[-1].file_id
    await _handle_receipt(message, session, order_id, file_id)
    await state.clear()


@router.message(UserStates.waiting_receipt, F.document)
async def receive_receipt_document(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    order_id = data.get("order_id")
    if not order_id:
        await message.answer("Заказ не найден.")
        await state.clear()
        return

    file_id = message.document.file_id
    await _handle_receipt(message, session, order_id, file_id)
    await state.clear()


@router.message(UserStates.waiting_receipt)
async def receipt_wrong_format(message: Message) -> None:
    await message.answer("Пожалуйста, отправьте чек как фото или файл.")


async def _handle_receipt(
    message: Message,
    session: AsyncSession,
    order_id: int,
    file_id: str,
) -> None:
    order = await repo.get_order(session, order_id)
    if not order or order.user_id != message.from_user.id:
        await message.answer("Заказ не найден.")
        return

    await repo.set_order_receipt(session, order_id, file_id)
    await _safe_log_event(
        session,
        "manual_receipt_uploaded",
        user_id=message.from_user.id,
        payload={"order_id": order_id},
    )
    await message.answer("Чек получен. Ожидайте подтверждение администратора.")

    order_with_product = await repo.get_order_with_product(session, order_id)
    if not order_with_product:
        return

    _, product = order_with_product
    admin_ids = message.bot.settings.admin_ids

    for admin_id in admin_ids:
        await message.bot.send_message(
            admin_id,
            (
                "Новый чек на проверку:\n"
                f"Пользователь: {message.from_user.id}\n"
                f"Товар: {product.name}\n"
                f"Сумма: {order.amount_rub} ₽\n"
                f"Заказ: #{order.id}"
            ),
            reply_markup=admin_confirm_order_kb(order.id),
        )
        if message.photo:
            await message.bot.send_photo(admin_id, photo=file_id, caption="Чек")
        else:
            await message.bot.send_document(admin_id, document=file_id, caption="Чек")

    # Admin confirmation buttons are handled in admin handlers


@router.callback_query(F.data.startswith("cancel_order:"))
async def cancel_order(callback: CallbackQuery, session: AsyncSession) -> None:
    order_id = int(callback.data.split(":")[1])
    order = await repo.get_order(session, order_id)
    if not order or order.user_id != callback.from_user.id:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    await repo.mark_order_status(session, order_id, OrderStatus.cancelled)
    await _safe_log_event(
        session,
        "payment_cancelled",
        user_id=callback.from_user.id,
        payload={"order_id": order_id},
    )
    crypto_enabled, card_enabled, ozon_enabled, yandex_enabled, yoomoney_enabled = await _get_payment_flags(session)
    if crypto_enabled or card_enabled or ozon_enabled or yandex_enabled or yoomoney_enabled:
        labels = await repo.get_button_labels(session)
        await callback.message.answer(
            "Заказ отменен. Выберите способ оплаты снова:",
            reply_markup=payment_methods_kb(
                order.product_id,
                crypto_enabled,
                card_enabled,
                ozon_enabled,
                yandex_enabled,
                yoomoney_enabled,
                labels=labels,
            ),
        )
    else:
        await callback.message.answer("Заказ отменен. Сейчас прием оплат отключен.")
    await callback.answer()
