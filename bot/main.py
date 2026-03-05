from __future__ import annotations

import asyncio
import contextlib
import hashlib
import logging
import os
from pathlib import Path

import aiohttp
import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import load_settings
from bot.database import repo
from bot.database.db import create_engine, create_sessionmaker, init_db
from bot.handlers import start, menu, catalog, payments
from bot.handlers.admin import menu as admin_menu
from bot.handlers.admin import products as admin_products
from bot.handlers.admin import payments as admin_payments
from bot.handlers.admin import intro as admin_intro
from bot.handlers.admin import orders as admin_orders
from bot.handlers.admin import broadcast as admin_broadcast
from bot.middlewares.db import DbSessionMiddleware
from bot.services.bot_profile import apply_bot_profile
from bot.services.cryptobot import CryptoBotClient
from bot.services.invoice_watcher import run_invoice_watcher


def _acquire_instance_lock(bot_token: str):
    """Prevent running multiple polling instances for the same bot token."""

    token_hash = hashlib.sha256(bot_token.encode("utf-8")).hexdigest()[:12]
    lock_path = Path(__file__).resolve().parent.parent / f".bot-main-{token_hash}.lock"
    lock_file = open(lock_path, "a+", encoding="utf-8")
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock_file.close()
        return None

    lock_file.seek(0)
    lock_file.truncate()
    lock_file.write(str(os.getpid()))
    lock_file.flush()
    return lock_file


def _release_instance_lock(lock_file) -> None:
    if not lock_file:
        return
    try:
        if os.name == "nt":
            import msvcrt

            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass
    finally:
        lock_file.close()


async def run_web_admin(host: str, port: int) -> None:
    """Run FastAPI admin panel in the same process as Telegram bot."""

    config = uvicorn.Config(
        "bot.web.app:app",
        host=host,
        port=port,
        loop="asyncio",
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


async def main() -> None:
    settings = load_settings()

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s:%(name)s:%(message)s",
    )

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
        runtime_bot_token = await repo.get_effective_bot_token(session, settings.bot_token)

    lock_file = _acquire_instance_lock(runtime_bot_token)
    if not lock_file:
        logging.error(
            "Another bot instance is already running for this token. Stop duplicate process first."
        )
        await engine.dispose()
        return

    try:

        bot = Bot(runtime_bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        async with sessionmaker() as session:
            profile_name = await repo.get_setting(
                session,
                repo.SETTING_BOT_PROFILE_NAME,
                default="",
            )
        try:
            await apply_bot_profile(bot, profile_name)
        except Exception:
            logging.exception("Failed to apply bot profile settings")
        dp = Dispatcher(storage=MemoryStorage())

        dp.update.middleware(DbSessionMiddleware(sessionmaker))

        dp.include_router(start.router)
        dp.include_router(menu.router)
        dp.include_router(catalog.router)
        dp.include_router(payments.router)
        dp.include_router(admin_menu.router)
        dp.include_router(admin_products.router)
        dp.include_router(admin_payments.router)
        dp.include_router(admin_intro.router)
        dp.include_router(admin_orders.router)
        dp.include_router(admin_broadcast.router)

        async with aiohttp.ClientSession() as http_session:
            crypto_client = CryptoBotClient(
                api_token=settings.cryptopay_api_token,
                base_url=settings.cryptopay_base_url,
                session=http_session,
            )

            bot.settings = settings
            bot.cryptobot = crypto_client

            watcher_task = asyncio.create_task(
                run_invoice_watcher(
                    bot,
                    sessionmaker,
                    crypto_client,
                    settings.crypto_check_interval,
                ),
                name="invoice_watcher",
            )

            logging.info(
                "Web admin started on http://%s:%s/admin",
                settings.web_admin_host,
                settings.web_admin_port,
            )

            bot_task = asyncio.create_task(dp.start_polling(bot), name="telegram_polling")
            web_task = asyncio.create_task(
                run_web_admin(settings.web_admin_host, settings.web_admin_port),
                name="web_admin",
            )

            try:
                done, _pending = await asyncio.wait(
                    {bot_task, web_task},
                    return_when=asyncio.FIRST_EXCEPTION,
                )
                for task in done:
                    exc = task.exception()
                    if exc:
                        raise exc
            finally:
                watcher_task.cancel()
                bot_task.cancel()
                web_task.cancel()
                with contextlib.suppress(Exception):
                    await asyncio.gather(watcher_task, bot_task, web_task, return_exceptions=True)
                await engine.dispose()
    finally:
        _release_instance_lock(lock_file)


if __name__ == "__main__":
    asyncio.run(main())
