from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.database.models import Product


BTN_CATALOG_DEFAULT = "💎Товары"
BTN_PROOFS_DEFAULT = "✅ Доказательства"
BTN_SUPPORT_DEFAULT = "🛠 Техподдержка"
BTN_ADMIN_DEFAULT = "⚙️Админка"
BTN_BUY_DEFAULT = "Купить"
BTN_BACK_DEFAULT = "Назад"
BTN_PAY_CRYPTO_DEFAULT = "CryptoBot"
BTN_PAY_CARD_DEFAULT = "Перевод/Карта"
BTN_PAY_OZON_DEFAULT = "Озон Банк"
BTN_PAY_YANDEX_DEFAULT = "Яндекс Банк"
BTN_PAY_YOOMONEY_DEFAULT = "ЮMoney"
BTN_I_PAID_DEFAULT = "Я оплатил"
BTN_CANCEL_ORDER_DEFAULT = "Отменить"


def _label(labels: dict[str, str] | None, key: str, default: str) -> str:
    if not labels:
        return default
    value = (labels.get(key) or "").strip()
    return value or default


def main_menu_kb(is_admin: bool, labels: dict[str, str] | None = None) -> ReplyKeyboardMarkup:
    catalog_text = _label(labels, "btn_catalog", BTN_CATALOG_DEFAULT)
    proofs_text = _label(labels, "btn_proofs", BTN_PROOFS_DEFAULT)
    support_text = _label(labels, "btn_support", BTN_SUPPORT_DEFAULT)
    admin_text = _label(labels, "btn_admin", BTN_ADMIN_DEFAULT)
    row = [
        KeyboardButton(text=catalog_text),
        KeyboardButton(text=proofs_text),
        KeyboardButton(text=support_text),
    ]
    if is_admin:
        row.append(KeyboardButton(text=admin_text))

    return ReplyKeyboardMarkup(
        keyboard=[row],
        resize_keyboard=True,
    )


def products_kb(products: list[Product]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for product in products:
        builder.add(
            InlineKeyboardButton(
                text=f"{product.name} — {product.price_rub} ₽",
                callback_data=f"product:{product.id}",
            )
        )
    builder.adjust(1)
    return builder.as_markup()


def product_detail_kb(product_id: int, labels: dict[str, str] | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    buy_text = _label(labels, "btn_buy", BTN_BUY_DEFAULT)
    back_text = _label(labels, "btn_back", BTN_BACK_DEFAULT)
    builder.add(
        InlineKeyboardButton(text=buy_text, callback_data=f"buy:{product_id}"),
        InlineKeyboardButton(text=back_text, callback_data="back_to_products"),
    )
    builder.adjust(1)
    return builder.as_markup()


def payment_methods_kb(
    product_id: int,
    crypto_enabled: bool,
    card_enabled: bool,
    ozon_enabled: bool,
    yandex_enabled: bool,
    yoomoney_enabled: bool,
    labels: dict[str, str] | None = None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    crypto_text = _label(labels, "btn_pay_crypto", BTN_PAY_CRYPTO_DEFAULT)
    card_text = _label(labels, "btn_pay_card", BTN_PAY_CARD_DEFAULT)
    ozon_text = _label(labels, "btn_pay_ozon", BTN_PAY_OZON_DEFAULT)
    yandex_text = _label(labels, "btn_pay_yandex", BTN_PAY_YANDEX_DEFAULT)
    yoomoney_text = _label(labels, "btn_pay_yoomoney", BTN_PAY_YOOMONEY_DEFAULT)
    back_text = _label(labels, "btn_back", BTN_BACK_DEFAULT)
    if crypto_enabled:
        builder.add(
            InlineKeyboardButton(
                text=crypto_text, callback_data=f"pay_crypto:{product_id}"
            )
        )
    if card_enabled:
        builder.add(
            InlineKeyboardButton(
                text=card_text, callback_data=f"pay_card:{product_id}"
            )
        )
    if ozon_enabled:
        builder.add(
            InlineKeyboardButton(
                text=ozon_text, callback_data=f"pay_ozon:{product_id}"
            )
        )
    if yandex_enabled:
        builder.add(
            InlineKeyboardButton(
                text=yandex_text, callback_data=f"pay_yandex:{product_id}"
            )
        )
    if yoomoney_enabled:
        builder.add(
            InlineKeyboardButton(
                text=yoomoney_text, callback_data=f"pay_yoomoney:{product_id}"
            )
        )
    builder.add(
        InlineKeyboardButton(text=back_text, callback_data=f"product:{product_id}")
    )
    builder.adjust(1)
    return builder.as_markup()


def crypto_invoice_kb(order_id: int, pay_url: str, labels: dict[str, str] | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    cancel_text = _label(labels, "btn_cancel_order", BTN_CANCEL_ORDER_DEFAULT)
    builder.add(
        InlineKeyboardButton(text="Оплатить", url=pay_url),
        InlineKeyboardButton(
            text="Проверить оплату", callback_data=f"check_crypto:{order_id}"
        ),
        InlineKeyboardButton(text=cancel_text, callback_data=f"cancel_order:{order_id}"),
    )
    builder.adjust(1)
    return builder.as_markup()


def manual_payment_kb(order_id: int, labels: dict[str, str] | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    i_paid_text = _label(labels, "btn_i_paid", BTN_I_PAID_DEFAULT)
    back_text = _label(labels, "btn_back", BTN_BACK_DEFAULT)
    builder.add(
        InlineKeyboardButton(text=i_paid_text, callback_data=f"manual_paid:{order_id}"),
        InlineKeyboardButton(text=back_text, callback_data="back_to_products"),
    )
    builder.adjust(1)
    return builder.as_markup()
