import asyncio

from bot.config import load_settings
from bot.database.db import create_engine, create_sessionmaker, init_db
from bot.database import repo


async def main() -> None:
    settings = load_settings()
    engine = create_engine(settings)
    sessionmaker = create_sessionmaker(engine)
    await init_db(engine)

    async with sessionmaker() as session:
        await repo.ensure_default_settings(
            session,
            intro_default=settings.intro_default,
            crypto_enabled=settings.crypto_payment_enabled_default,
            manual_enabled=settings.manual_payment_enabled_default,
            manual_instructions=settings.manual_payment_instructions_default,
        )

        # Example product
        existing = await repo.list_products(session, active_only=False)
        if not existing:
            await repo.create_product(
                session,
                name="Пример товара",
                price_rub=999,
                description="Это демонстрационный товар. Замените его на реальные позиции.",
                photo_file_id="https://placehold.co/800x600/png",
                media_type="photo",
                content="https://example.com/your-product-link",
            )

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
