from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy import and_, delete, desc, distinct, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import BotEvent, Order, OrderStatus, PaymentMethod, Product, Setting, User


SETTING_INTRO = "intro_message"
SETTING_INTRO_PHOTO = "intro_photo"
SETTING_INTRO_MEDIA_TYPE = "intro_media_type"
SETTING_CRYPTO_ENABLED = "payment_crypto_enabled"
SETTING_MANUAL_ENABLED = "payment_manual_enabled"
SETTING_MANUAL_INSTRUCTIONS = "payment_manual_instructions"
SETTING_OZON_ENABLED = "payment_ozon_enabled"
SETTING_OZON_INSTRUCTIONS = "payment_ozon_instructions"
SETTING_YANDEX_ENABLED = "payment_yandex_enabled"
SETTING_YANDEX_INSTRUCTIONS = "payment_yandex_instructions"
SETTING_YOOMONEY_ENABLED = "payment_yoomoney_enabled"
SETTING_YOOMONEY_INSTRUCTIONS = "payment_yoomoney_instructions"
SETTING_BTN_CATALOG = "btn_catalog"
SETTING_BTN_PROOFS = "btn_proofs"
SETTING_PROOFS_ENABLED = "proofs_enabled"
SETTING_BTN_SUPPORT = "btn_support"
SETTING_BTN_ADMIN = "btn_admin"
SETTING_BTN_BUY = "btn_buy"
SETTING_BTN_BACK = "btn_back"
SETTING_BTN_PAY_CRYPTO = "btn_pay_crypto"
SETTING_BTN_PAY_CARD = "btn_pay_card"
SETTING_BTN_PAY_OZON = "btn_pay_ozon"
SETTING_BTN_PAY_YANDEX = "btn_pay_yandex"
SETTING_BTN_PAY_YOOMONEY = "btn_pay_yoomoney"
SETTING_BTN_I_PAID = "btn_i_paid"
SETTING_BTN_CANCEL_ORDER = "btn_cancel_order"
SETTING_STATS_RESET_AT = "stats_reset_at"
SETTING_SUPPORT_CONTACT = "support_contact"
SETTING_PROOFS_TEXT = "proofs_text"


async def upsert_user(session: AsyncSession, tg_id: int, username: str | None, full_name: str | None) -> None:
    payload = {
        "id": tg_id,
        "username": username,
        "full_name": full_name,
        "is_blocked": False,
    }

    bind = session.get_bind()
    dialect_name = bind.dialect.name if bind is not None else ""

    if dialect_name == "sqlite":
        stmt = sqlite_insert(User).values(**payload).on_conflict_do_update(
            index_elements=[User.id],
            set_={"username": username, "full_name": full_name},
        )
        await session.execute(stmt)
        await session.commit()
        return

    if dialect_name == "postgresql":
        stmt = pg_insert(User).values(**payload).on_conflict_do_update(
            index_elements=[User.id],
            set_={"username": username, "full_name": full_name},
        )
        await session.execute(stmt)
        await session.commit()
        return

    # Generic fallback for other SQL dialects.
    try:
        updated = await session.execute(
            update(User)
            .where(User.id == tg_id)
            .values(username=username, full_name=full_name)
        )
        if updated.rowcount == 0:
            session.add(User(**payload))
        await session.commit()
    except IntegrityError:
        await session.rollback()
        await session.execute(
            update(User)
            .where(User.id == tg_id)
            .values(username=username, full_name=full_name)
        )
        await session.commit()


async def list_users(session: AsyncSession, include_blocked: bool = False) -> list[User]:
    query = select(User)
    if not include_blocked:
        query = query.where(User.is_blocked.is_(False))
    result = await session.execute(query)
    return list(result.scalars().all())


async def set_user_blocked(session: AsyncSession, tg_id: int, blocked: bool) -> None:
    await session.execute(
        update(User)
        .where(User.id == tg_id)
        .values(is_blocked=blocked)
    )
    await session.commit()


async def get_setting(session: AsyncSession, key: str, default: str | None = None) -> str | None:
    setting = await session.get(Setting, key)
    if setting:
        return setting.value
    return default


async def set_setting(session: AsyncSession, key: str, value: str) -> None:
    setting = await session.get(Setting, key)
    if setting:
        setting.value = value
    else:
        session.add(Setting(key=key, value=value))
    await session.commit()


async def ensure_default_settings(
    session: AsyncSession,
    intro_default: str,
    crypto_enabled: bool,
    manual_enabled: bool,
    manual_instructions: str,
) -> None:
    defaults = {
        SETTING_INTRO: intro_default,
        SETTING_INTRO_PHOTO: "",
        SETTING_INTRO_MEDIA_TYPE: "none",
        SETTING_CRYPTO_ENABLED: "1" if crypto_enabled else "0",
        SETTING_MANUAL_ENABLED: "1" if manual_enabled else "0",
        SETTING_MANUAL_INSTRUCTIONS: manual_instructions,
        SETTING_OZON_ENABLED: "0",
        SETTING_OZON_INSTRUCTIONS: "Оплатите через Озон Банк и пришлите чек.",
        SETTING_YANDEX_ENABLED: "0",
        SETTING_YANDEX_INSTRUCTIONS: "Оплатите через Яндекс Банк и пришлите чек.",
        SETTING_YOOMONEY_ENABLED: "0",
        SETTING_YOOMONEY_INSTRUCTIONS: "Оплатите через ЮMoney и пришлите чек.",
        SETTING_BTN_CATALOG: "💎Товары",
        SETTING_BTN_PROOFS: "✅ Доказательства",
        SETTING_PROOFS_ENABLED: "1",
        SETTING_BTN_SUPPORT: "🛠 Техподдержка",
        SETTING_BTN_ADMIN: "⚙️Админка",
        SETTING_BTN_BUY: "Купить",
        SETTING_BTN_BACK: "Назад",
        SETTING_BTN_PAY_CRYPTO: "CryptoBot",
        SETTING_BTN_PAY_CARD: "Перевод/Карта",
        SETTING_BTN_PAY_OZON: "Озон Банк",
        SETTING_BTN_PAY_YANDEX: "Яндекс Банк",
        SETTING_BTN_PAY_YOOMONEY: "ЮMoney",
        SETTING_BTN_I_PAID: "Я оплатил",
        SETTING_BTN_CANCEL_ORDER: "Отменить",
        SETTING_STATS_RESET_AT: "",
        SETTING_SUPPORT_CONTACT: "@support",
        SETTING_PROOFS_TEXT: "Добавьте сюда ваши доказательства/отзывы.",
    }

    for key, value in defaults.items():
        if await session.get(Setting, key) is None:
            session.add(Setting(key=key, value=value))

    await session.commit()


async def get_button_labels(session: AsyncSession) -> dict[str, str]:
    defaults = {
        SETTING_BTN_CATALOG: "💎Товары",
        SETTING_BTN_PROOFS: "✅ Доказательства",
        SETTING_BTN_SUPPORT: "🛠 Техподдержка",
        SETTING_BTN_ADMIN: "⚙️Админка",
        SETTING_BTN_BUY: "Купить",
        SETTING_BTN_BACK: "Назад",
        SETTING_BTN_PAY_CRYPTO: "CryptoBot",
        SETTING_BTN_PAY_CARD: "Перевод/Карта",
        SETTING_BTN_PAY_OZON: "Озон Банк",
        SETTING_BTN_PAY_YANDEX: "Яндекс Банк",
        SETTING_BTN_PAY_YOOMONEY: "ЮMoney",
        SETTING_BTN_I_PAID: "Я оплатил",
        SETTING_BTN_CANCEL_ORDER: "Отменить",
    }
    data: dict[str, str] = {}
    for key, fallback in defaults.items():
        value = await get_setting(session, key, default=fallback)
        data[key] = (value or "").strip() or fallback
    return data


async def reset_analytics_period(session: AsyncSession) -> None:
    await set_setting(session, SETTING_STATS_RESET_AT, datetime.utcnow().isoformat())


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.strip())
    except ValueError:
        return None


async def get_analytics_reset_at(session: AsyncSession) -> datetime | None:
    raw = await get_setting(session, SETTING_STATS_RESET_AT, default="")
    return _parse_datetime(raw)


async def list_products(session: AsyncSession, active_only: bool = True) -> list[Product]:
    query = select(Product)
    if active_only:
        query = query.where(Product.is_active.is_(True))
    query = query.order_by(Product.id.asc())
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_product(session: AsyncSession, product_id: int) -> Product | None:
    return await session.get(Product, product_id)


async def create_product(
    session: AsyncSession,
    name: str,
    price_rub: int,
    description: str,
    photo_file_id: str,
    media_type: str,
    content: str,
    price_stars: int | None = None,
) -> Product:
    product = Product(
        name=name,
        price_rub=price_rub,
        price_stars=price_stars,
        description=description,
        photo_file_id=photo_file_id,
        media_type=media_type,
        content=content,
        is_active=True,
    )
    session.add(product)
    await session.commit()
    await session.refresh(product)
    return product


async def update_product(session: AsyncSession, product_id: int, **fields) -> None:
    await session.execute(update(Product).where(Product.id == product_id).values(**fields))
    await session.commit()


async def delete_product(session: AsyncSession, product_id: int) -> str:
    has_orders = await session.execute(
        select(Order.id).where(Order.product_id == product_id).limit(1)
    )
    if has_orders.first():
        await session.execute(
            update(Product)
            .where(Product.id == product_id)
            .values(is_active=False)
        )
        await session.commit()
        return "archived"

    await session.execute(delete(Product).where(Product.id == product_id))
    await session.commit()
    return "deleted"


async def create_order(
    session: AsyncSession,
    user_id: int,
    product_id: int,
    amount_rub: int,
    payment_method: PaymentMethod,
    status: OrderStatus,
) -> Order:
    order = Order(
        user_id=user_id,
        product_id=product_id,
        amount_rub=amount_rub,
        payment_method=payment_method,
        status=status,
    )
    session.add(order)
    await session.commit()
    await session.refresh(order)
    return order


async def delete_order(session: AsyncSession, order_id: int) -> bool:
    result = await session.execute(delete(Order).where(Order.id == order_id))
    await session.commit()
    return bool(result.rowcount and result.rowcount > 0)


async def clear_orders(session: AsyncSession) -> int:
    result = await session.execute(delete(Order))
    await session.commit()
    return int(result.rowcount or 0)


async def clear_events(session: AsyncSession) -> int:
    result = await session.execute(delete(BotEvent))
    await session.commit()
    return int(result.rowcount or 0)




async def get_order(session: AsyncSession, order_id: int) -> Order | None:
    return await session.get(Order, order_id)


async def get_order_with_product(session: AsyncSession, order_id: int) -> tuple[Order, Product] | None:
    result = await session.execute(
        select(Order, Product)
        .join(Product, Product.id == Order.product_id)
        .where(Order.id == order_id)
    )
    row = result.first()
    if not row:
        return None
    return row[0], row[1]


async def set_order_invoice(session: AsyncSession, order_id: int, invoice_id: str, pay_url: str) -> None:
    await session.execute(
        update(Order)
        .where(Order.id == order_id)
        .values(crypto_invoice_id=invoice_id, crypto_invoice_url=pay_url)
    )
    await session.commit()


async def set_order_receipt(session: AsyncSession, order_id: int, receipt_file_id: str) -> None:
    await session.execute(
        update(Order)
        .where(Order.id == order_id)
        .values(receipt_file_id=receipt_file_id, status=OrderStatus.waiting_admin)
    )
    await session.commit()


async def mark_order_status(session: AsyncSession, order_id: int, status: OrderStatus) -> None:
    values = {"status": status}
    if status == OrderStatus.paid:
        values["paid_at"] = datetime.utcnow()
    await session.execute(update(Order).where(Order.id == order_id).values(**values))
    await session.commit()


async def list_orders(session: AsyncSession, limit: int = 20) -> list[Order]:
    result = await session.execute(
        select(Order).order_by(desc(Order.created_at)).limit(limit)
    )
    return list(result.scalars().all())


async def list_pending_crypto_orders(session: AsyncSession) -> list[Order]:
    result = await session.execute(
        select(Order)
        .where(
            and_(
                Order.payment_method == PaymentMethod.crypto,
                Order.status == OrderStatus.pending,
                Order.crypto_invoice_id.is_not(None),
            )
        )
    )
    return list(result.scalars().all())


async def log_event(
    session: AsyncSession,
    event_type: str,
    user_id: int | None = None,
    payload: dict | None = None,
) -> None:
    event = BotEvent(
        event_type=event_type,
        user_id=user_id,
        payload=json.dumps(payload, ensure_ascii=False) if payload else None,
    )
    session.add(event)
    await session.commit()


async def get_analytics_summary(session: AsyncSession) -> dict:
    now = datetime.utcnow()
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)
    reset_at = await get_analytics_reset_at(session)
    reset_at_iso = reset_at.isoformat(timespec="seconds") if reset_at else ""

    event_period_filter = BotEvent.created_at >= reset_at if reset_at else None
    paid_period_filter = Order.paid_at >= reset_at if reset_at else None
    created_period_filter = Order.created_at >= reset_at if reset_at else None

    users_total = await session.scalar(select(func.count(User.id)))
    users_period = await session.scalar(
        select(func.count(User.id)).where(User.created_at >= reset_at)
    ) if reset_at else users_total
    starts_total = await session.scalar(
        select(func.count(BotEvent.id)).where(
            and_(
                BotEvent.event_type == "start",
                event_period_filter if event_period_filter is not None else True,
            )
        )
    )
    starts_24h = await session.scalar(
        select(func.count(BotEvent.id)).where(
            and_(
                BotEvent.event_type == "start",
                BotEvent.created_at >= day_ago,
                event_period_filter if event_period_filter is not None else True,
            )
        )
    )
    unique_24h = await session.scalar(
        select(func.count(distinct(BotEvent.user_id))).where(
            and_(
                BotEvent.event_type == "start",
                BotEvent.created_at >= day_ago,
                event_period_filter if event_period_filter is not None else True,
            )
        )
    )
    catalog_views = await session.scalar(
        select(func.count(BotEvent.id)).where(
            and_(
                BotEvent.event_type == "catalog_view",
                event_period_filter if event_period_filter is not None else True,
            )
        )
    )
    product_views = await session.scalar(
        select(func.count(BotEvent.id)).where(
            and_(
                BotEvent.event_type == "product_view",
                event_period_filter if event_period_filter is not None else True,
            )
        )
    )
    payment_attempts = await session.scalar(
        select(func.count(BotEvent.id)).where(
            and_(
                BotEvent.event_type.like("payment_start_%"),
                event_period_filter if event_period_filter is not None else True,
            )
        )
    )

    paid_orders_total = await session.scalar(
        select(func.count(Order.id)).where(
            and_(
                Order.status == OrderStatus.paid,
                paid_period_filter if paid_period_filter is not None else True,
            )
        )
    )
    paid_orders_24h = await session.scalar(
        select(func.count(Order.id)).where(
            and_(
                Order.status == OrderStatus.paid,
                Order.paid_at.is_not(None),
                Order.paid_at >= day_ago,
                paid_period_filter if paid_period_filter is not None else True,
            )
        )
    )
    paid_orders_7d = await session.scalar(
        select(func.count(Order.id)).where(
            and_(
                Order.status == OrderStatus.paid,
                Order.paid_at.is_not(None),
                Order.paid_at >= week_ago,
                paid_period_filter if paid_period_filter is not None else True,
            )
        )
    )
    orders_total = await session.scalar(
        select(func.count(Order.id)).where(
            and_(created_period_filter if created_period_filter is not None else True)
        )
    )
    conversion_rate = (
        round((paid_orders_total or 0) * 100 / (orders_total or 1), 2)
        if (orders_total or 0) > 0
        else 0.0
    )
    paid_crypto = await session.scalar(
        select(func.count(Order.id)).where(
            and_(
                Order.status == OrderStatus.paid,
                Order.payment_method == PaymentMethod.crypto,
                paid_period_filter if paid_period_filter is not None else True,
            )
        )
    )
    paid_card = await session.scalar(
        select(func.count(Order.id)).where(
            and_(
                Order.status == OrderStatus.paid,
                Order.payment_method.in_([PaymentMethod.manual, PaymentMethod.manual_card]),
                paid_period_filter if paid_period_filter is not None else True,
            )
        )
    )
    paid_ozon = await session.scalar(
        select(func.count(Order.id)).where(
            and_(
                Order.status == OrderStatus.paid,
                Order.payment_method == PaymentMethod.manual_ozon,
                paid_period_filter if paid_period_filter is not None else True,
            )
        )
    )
    paid_yandex = await session.scalar(
        select(func.count(Order.id)).where(
            and_(
                Order.status == OrderStatus.paid,
                Order.payment_method == PaymentMethod.manual_yandex,
                paid_period_filter if paid_period_filter is not None else True,
            )
        )
    )
    paid_yoomoney = await session.scalar(
        select(func.count(Order.id)).where(
            and_(
                Order.status == OrderStatus.paid,
                Order.payment_method == PaymentMethod.manual_yoomoney,
                paid_period_filter if paid_period_filter is not None else True,
            )
        )
    )
    revenue_total = await session.scalar(
        select(func.coalesce(func.sum(Order.amount_rub), 0)).where(
            and_(
                Order.status == OrderStatus.paid,
                paid_period_filter if paid_period_filter is not None else True,
            )
        )
    )
    revenue_24h = await session.scalar(
        select(func.coalesce(func.sum(Order.amount_rub), 0)).where(
            and_(
                Order.status == OrderStatus.paid,
                Order.paid_at.is_not(None),
                Order.paid_at >= day_ago,
                paid_period_filter if paid_period_filter is not None else True,
            )
        )
    )
    revenue_7d = await session.scalar(
        select(func.coalesce(func.sum(Order.amount_rub), 0)).where(
            and_(
                Order.status == OrderStatus.paid,
                Order.paid_at.is_not(None),
                Order.paid_at >= week_ago,
                paid_period_filter if paid_period_filter is not None else True,
            )
        )
    )
    top_products_result = await session.execute(
        select(Product.name, func.count(Order.id).label("qty"))
        .join(Order, Order.product_id == Product.id)
        .where(
            and_(
                Order.status == OrderStatus.paid,
                paid_period_filter if paid_period_filter is not None else True,
            )
        )
        .group_by(Product.id, Product.name)
        .order_by(desc(func.count(Order.id)))
        .limit(5)
    )
    top_products = [
        {"name": row[0], "qty": int(row[1] or 0)}
        for row in top_products_result.fetchall()
    ]

    return {
        "reset_at": reset_at_iso,
        "users_total": int(users_total or 0),
        "users_period": int(users_period or 0),
        "starts_total": int(starts_total or 0),
        "starts_24h": int(starts_24h or 0),
        "unique_24h": int(unique_24h or 0),
        "catalog_views": int(catalog_views or 0),
        "product_views": int(product_views or 0),
        "payment_attempts": int(payment_attempts or 0),
        "orders_total": int(orders_total or 0),
        "conversion_rate": conversion_rate,
        "paid_orders_total": int(paid_orders_total or 0),
        "paid_orders_24h": int(paid_orders_24h or 0),
        "paid_orders_7d": int(paid_orders_7d or 0),
        "paid_crypto": int(paid_crypto or 0),
        "paid_card": int(paid_card or 0),
        "paid_ozon": int(paid_ozon or 0),
        "paid_yandex": int(paid_yandex or 0),
        "paid_yoomoney": int(paid_yoomoney or 0),
        "revenue_total": int(revenue_total or 0),
        "revenue_24h": int(revenue_24h or 0),
        "revenue_7d": int(revenue_7d or 0),
        "top_products": top_products,
    }


async def get_recent_events(session: AsyncSession, limit: int = 20) -> list[BotEvent]:
    result = await session.execute(
        select(BotEvent).order_by(desc(BotEvent.created_at)).limit(limit)
    )
    return list(result.scalars().all())
