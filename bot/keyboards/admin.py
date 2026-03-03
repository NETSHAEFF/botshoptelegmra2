from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.database.models import Order, Product


def admin_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="Товары", callback_data="admin_products"),
        InlineKeyboardButton(text="Вступительное сообщение", callback_data="admin_intro"),
        InlineKeyboardButton(text="Способы оплаты", callback_data="admin_payments"),
        InlineKeyboardButton(text="Заказы", callback_data="admin_orders"),
        InlineKeyboardButton(text="Рассылка", callback_data="admin_broadcast"),
    )
    builder.adjust(1)
    return builder.as_markup()


def admin_products_kb(products: list[Product]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for product in products:
        builder.add(
            InlineKeyboardButton(
                text=f"{product.id}. {product.name}",
                callback_data=f"admin_product:{product.id}",
            )
        )
    builder.add(InlineKeyboardButton(text="Добавить товар", callback_data="admin_add_product"))
    builder.add(InlineKeyboardButton(text="Назад", callback_data="admin_back"))
    builder.adjust(1)
    return builder.as_markup()


def admin_product_actions_kb(product_id: int, is_active: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="Изменить название", callback_data=f"admin_edit_name:{product_id}"),
        InlineKeyboardButton(text="Изменить цену", callback_data=f"admin_edit_price:{product_id}"),
        InlineKeyboardButton(text="Изменить описание", callback_data=f"admin_edit_desc:{product_id}"),
        InlineKeyboardButton(text="Изменить фото", callback_data=f"admin_edit_photo:{product_id}"),
        InlineKeyboardButton(text="Изменить контент", callback_data=f"admin_edit_content:{product_id}"),
        InlineKeyboardButton(
            text="Деактивировать" if is_active else "Активировать",
            callback_data=f"admin_toggle_active:{product_id}",
        ),
        InlineKeyboardButton(text="Удалить", callback_data=f"admin_delete:{product_id}"),
        InlineKeyboardButton(text="Назад", callback_data="admin_products"),
    )
    builder.adjust(1)
    return builder.as_markup()


def admin_payments_kb(
    crypto_enabled: bool,
    card_enabled: bool,
    ozon_enabled: bool,
    yandex_enabled: bool,
    yoomoney_enabled: bool,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(
            text=f"CryptoBot: {'ON' if crypto_enabled else 'OFF'}",
            callback_data="admin_toggle_crypto",
        ),
        InlineKeyboardButton(
            text=f"Перевод/Карта: {'ON' if card_enabled else 'OFF'}",
            callback_data="admin_toggle_card",
        ),
        InlineKeyboardButton(
            text=f"Озон Банк: {'ON' if ozon_enabled else 'OFF'}",
            callback_data="admin_toggle_ozon",
        ),
        InlineKeyboardButton(
            text=f"Яндекс Банк: {'ON' if yandex_enabled else 'OFF'}",
            callback_data="admin_toggle_yandex",
        ),
        InlineKeyboardButton(
            text=f"ЮMoney: {'ON' if yoomoney_enabled else 'OFF'}",
            callback_data="admin_toggle_yoomoney",
        ),
        InlineKeyboardButton(
            text="Реквизиты Перевод/Карта",
            callback_data="admin_edit_card_instructions",
        ),
        InlineKeyboardButton(
            text="Реквизиты Озон Банк",
            callback_data="admin_edit_ozon_instructions",
        ),
        InlineKeyboardButton(
            text="Реквизиты Яндекс Банк",
            callback_data="admin_edit_yandex_instructions",
        ),
        InlineKeyboardButton(
            text="Реквизиты ЮMoney",
            callback_data="admin_edit_yoomoney_instructions",
        ),
        InlineKeyboardButton(text="Назад", callback_data="admin_back"),
    )
    builder.adjust(1)
    return builder.as_markup()


def admin_orders_kb(orders: list[Order]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for order in orders:
        if order.status.value == "waiting_admin":
            builder.add(
                InlineKeyboardButton(
                    text=f"Подтвердить #{order.id}",
                    callback_data=f"admin_confirm:{order.id}",
                )
            )
    builder.add(InlineKeyboardButton(text="Назад", callback_data="admin_back"))
    builder.adjust(1)
    return builder.as_markup()


def admin_confirm_order_kb(order_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="Подтвердить оплату", callback_data=f"admin_confirm:{order_id}"),
        InlineKeyboardButton(text="Назад", callback_data="admin_orders"),
    )
    builder.adjust(1)
    return builder.as_markup()


def admin_broadcast_confirm_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="Отправить", callback_data="admin_broadcast_send"),
        InlineKeyboardButton(text="Отмена", callback_data="admin_back"),
    )
    builder.adjust(1)
    return builder.as_markup()


def admin_cancel_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Назад", callback_data="admin_cancel"))
    builder.adjust(1)
    return builder.as_markup()


def admin_intro_kb(has_photo: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="Изменить текст", callback_data="admin_intro_set_text"),
        InlineKeyboardButton(text="Изменить фото", callback_data="admin_intro_set_photo"),
    )
    if has_photo:
        builder.add(
            InlineKeyboardButton(
                text="Удалить фото",
                callback_data="admin_intro_remove_photo",
            )
        )
    builder.add(InlineKeyboardButton(text="Назад", callback_data="admin_back"))
    builder.adjust(1)
    return builder.as_markup()
