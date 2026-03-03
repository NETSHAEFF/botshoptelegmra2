from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class OrderStatus(str, enum.Enum):
    pending = "pending"  # crypto invoice created, awaiting payment
    waiting_receipt = "waiting_receipt"  # user clicked "I paid" but has not sent receipt yet
    waiting_admin = "waiting_admin"  # receipt sent, admin review required
    paid = "paid"
    cancelled = "cancelled"
    expired = "expired"


class PaymentMethod(str, enum.Enum):
    crypto = "crypto"
    stars = "stars"  # legacy, disabled in current flow
    manual = "manual"
    manual_card = "manual_card"
    manual_ozon = "manual_ozon"
    manual_yandex = "manual_yandex"
    manual_yoomoney = "manual_yoomoney"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    orders: Mapped[list["Order"]] = relationship(back_populates="user")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    price_rub: Mapped[int] = mapped_column(Integer)
    price_stars: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str] = mapped_column(Text)
    photo_file_id: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(16), default="photo")
    content: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    orders: Mapped[list["Order"]] = relationship(back_populates="product")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id"))

    amount_rub: Mapped[int] = mapped_column(Integer)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status"),
        default=OrderStatus.pending,
    )
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, name="payment_method"),
    )

    crypto_invoice_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    crypto_invoice_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    receipt_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="orders")
    product: Mapped[Product] = relationship(back_populates="orders")


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)


class BotEvent(Base):
    __tablename__ = "bot_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
