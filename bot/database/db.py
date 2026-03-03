from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.config import Settings
from bot.database.models import Base


def create_engine(settings: Settings):
    return create_async_engine(settings.database_url, echo=False, future=True)


def create_sessionmaker(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db(engine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _apply_sqlite_migrations(conn)


async def _apply_sqlite_migrations(conn) -> None:
    """Lightweight migrations for SQLite only (no Alembic)."""

    if conn.dialect.name != "sqlite":
        return

    result = await conn.exec_driver_sql("PRAGMA table_info(products)")
    columns = {row[1] for row in result.fetchall()}
    if "price_stars" not in columns:
        await conn.exec_driver_sql("ALTER TABLE products ADD COLUMN price_stars INTEGER")
    if "media_type" not in columns:
        await conn.exec_driver_sql("ALTER TABLE products ADD COLUMN media_type TEXT DEFAULT 'photo'")

    # Replace known invalid seed placeholder to keep catalog photo rendering stable.
    await conn.exec_driver_sql(
        "UPDATE products SET photo_file_id = ? WHERE photo_file_id = ?",
        ("https://placehold.co/800x600/png", "FILE_ID_FROM_TELEGRAM"),
    )
