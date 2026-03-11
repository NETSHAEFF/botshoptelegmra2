from __future__ import annotations

import hmac
from contextlib import suppress
from pathlib import Path

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BufferedInputFile
from fastapi import Depends, FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.sessions import SessionMiddleware

from bot.config import load_settings
from bot.database import repo
from bot.database.db import create_engine, create_sessionmaker, init_db
from bot.database.models import OrderStatus
from bot.services.broadcaster import broadcast_message
from bot.services.text_format import format_text

settings = load_settings()
engine = create_engine(settings)
sessionmaker = create_sessionmaker(engine)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="Bot Shop Admin")
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.web_admin_secret,
    same_site="lax",
    https_only=False,
)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


async def get_session():
    async with sessionmaker() as session:
        yield session


def is_logged_in(request: Request) -> bool:
    return bool(request.session.get("admin_auth"))


def set_flash(request: Request, text: str, level: str = "info") -> None:
    request.session["flash"] = {"text": text, "level": level}


def pop_flash(request: Request) -> dict | None:
    return request.session.pop("flash", None)


def render(request: Request, template_name: str, context: dict) -> HTMLResponse:
    payload = {
        "request": request,
        "flash": pop_flash(request),
        "is_auth": is_logged_in(request),
    }
    payload.update(context)
    return templates.TemplateResponse(template_name, payload)


def redirect(path: str) -> RedirectResponse:
    return RedirectResponse(url=path, status_code=303)


async def upload_media_to_telegram(upload: UploadFile | None) -> tuple[str, str] | None:
    if not upload or not upload.filename:
        return None
    if not settings.admin_ids:
        raise RuntimeError("ADMIN_IDS не настроен, нет чата для получения file_id.")

    payload = await upload.read()
    if not payload:
        raise RuntimeError("Загруженный файл пуст.")

    content_type = (upload.content_type or "").lower()
    media_type = "document"
    if content_type.startswith("image/"):
        if "gif" in content_type:
            media_type = "animation"
        else:
            media_type = "photo"
    elif content_type.startswith("video/"):
        media_type = "video"

    bot = Bot(
        settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    try:
        file = BufferedInputFile(payload, filename=upload.filename or "upload.bin")
        chat_id = settings.admin_ids[0]
        if media_type == "photo":
            message = await bot.send_photo(chat_id=chat_id, photo=file, caption="Web admin upload")
            file_id = message.photo[-1].file_id
        elif media_type == "video":
            message = await bot.send_video(chat_id=chat_id, video=file, caption="Web admin upload")
            file_id = message.video.file_id
        elif media_type == "animation":
            message = await bot.send_animation(chat_id=chat_id, animation=file, caption="Web admin upload")
            file_id = message.animation.file_id
        else:
            message = await bot.send_document(chat_id=chat_id, document=file, caption="Web admin upload")
            file_id = message.document.file_id

        with suppress(Exception):
            await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
        return media_type, file_id
    finally:
        await bot.session.close()


@app.on_event("startup")
async def startup() -> None:
    await init_db(engine)
    async with sessionmaker() as session:
        await repo.ensure_default_settings(
            session,
            intro_default=settings.intro_default,
            crypto_enabled=settings.crypto_payment_enabled_default,
            manual_enabled=settings.manual_payment_enabled_default,
            manual_instructions=settings.manual_payment_instructions_default,
        )


@app.on_event("shutdown")
async def shutdown() -> None:
    await engine.dispose()


@app.get("/")
async def index() -> RedirectResponse:
    return redirect("/admin")


@app.get("/admin/login", response_class=HTMLResponse)
async def login_page(request: Request) -> HTMLResponse:
    if is_logged_in(request):
        return redirect("/admin")
    return render(request, "login.html", {})


@app.post("/admin/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
) -> RedirectResponse:
    user_ok = hmac.compare_digest(username, settings.web_admin_username)
    pass_ok = hmac.compare_digest(password, settings.web_admin_password)
    if not (user_ok and pass_ok):
        set_flash(request, "Неверный логин или пароль.", "error")
        return redirect("/admin/login")

    request.session["admin_auth"] = True
    set_flash(request, "Вход выполнен.", "success")
    return redirect("/admin")


@app.post("/admin/logout")
async def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return redirect("/admin/login")


@app.get("/admin", response_class=HTMLResponse)
async def dashboard(request: Request, session: AsyncSession = Depends(get_session)):
    if not is_logged_in(request):
        return redirect("/admin/login")

    products = await repo.list_products(session, active_only=False)
    orders = await repo.list_orders(session, limit=500)
    waiting = [x for x in orders if x.status.value == "waiting_admin"]
    analytics = await repo.get_analytics_summary(session)
    recent_events = await repo.get_recent_events(session, limit=25)

    return render(
        request,
        "dashboard.html",
        {
            "products_count": len(products),
            "orders_count": len(orders),
            "waiting_count": len(waiting),
            "analytics": analytics,
            "recent_events": recent_events,
            "stats_reset_at": analytics.get("reset_at", ""),
        },
    )


@app.get("/admin/products", response_class=HTMLResponse)
async def products_page(request: Request, session: AsyncSession = Depends(get_session)):
    if not is_logged_in(request):
        return redirect("/admin/login")

    products = await repo.list_products(session, active_only=False)
    return render(request, "products.html", {"products": products})


@app.get("/admin/products/new", response_class=HTMLResponse)
async def product_new_page(request: Request):
    if not is_logged_in(request):
        return redirect("/admin/login")

    return render(
        request,
        "product_form.html",
        {
            "title": "Новый товар",
            "action": "/admin/products/new",
            "product": None,
        },
    )


@app.post("/admin/products/new")
async def product_new(
    request: Request,
    session: AsyncSession = Depends(get_session),
    name: str = Form(...),
    price_rub: int = Form(...),
    description: str = Form(...),
    photo_file_id: str = Form(""),
    media_type: str = Form("photo"),
    no_media: str | None = Form(None),
    photo_upload: UploadFile | None = File(default=None),
    content: str = Form(...),
    is_active: str | None = Form(None),
) -> RedirectResponse:
    if not is_logged_in(request):
        return redirect("/admin/login")

    photo_value = photo_file_id.strip()
    media_type_value = (media_type or "photo").strip().lower()
    if media_type_value not in {"photo", "video", "animation", "document", "none"}:
        media_type_value = "photo"

    if no_media is not None:
        photo_value = ""
        media_type_value = "none"
    if photo_upload and photo_upload.filename:
        try:
            uploaded = await upload_media_to_telegram(photo_upload)
            if uploaded:
                media_type_value, photo_value = uploaded
        except Exception as exc:
            set_flash(request, f"Ошибка загрузки медиа: {exc}", "error")
            return redirect("/admin/products/new")
    if not photo_value and media_type_value != "none":
        set_flash(request, "Укажите file_id/URL, либо загрузите медиа, либо включите режим без медиа.", "error")
        return redirect("/admin/products/new")

    product = await repo.create_product(
        session,
        name=name.strip(),
        price_rub=int(price_rub),
        description=description.strip(),
        photo_file_id=photo_value,
        media_type=media_type_value,
        content=content.strip(),
    )
    if is_active is None:
        await repo.update_product(session, product.id, is_active=False)

    set_flash(request, "Товар создан.", "success")
    return redirect("/admin/products")


@app.get("/admin/products/{product_id}/edit", response_class=HTMLResponse)
async def product_edit_page(
    request: Request,
    product_id: int,
    session: AsyncSession = Depends(get_session),
):
    if not is_logged_in(request):
        return redirect("/admin/login")

    product = await repo.get_product(session, product_id)
    if not product:
        set_flash(request, "Товар не найден.", "error")
        return redirect("/admin/products")

    return render(
        request,
        "product_form.html",
        {
            "title": f"Редактирование товара #{product.id}",
            "action": f"/admin/products/{product.id}/edit",
            "product": product,
        },
    )


@app.post("/admin/products/{product_id}/edit")
async def product_edit(
    request: Request,
    product_id: int,
    session: AsyncSession = Depends(get_session),
    name: str = Form(...),
    price_rub: int = Form(...),
    description: str = Form(...),
    photo_file_id: str = Form(""),
    media_type: str = Form("photo"),
    no_media: str | None = Form(None),
    photo_upload: UploadFile | None = File(default=None),
    content: str = Form(...),
    is_active: str | None = Form(None),
) -> RedirectResponse:
    if not is_logged_in(request):
        return redirect("/admin/login")

    existing = await repo.get_product(session, product_id)
    if not existing:
        set_flash(request, "Товар не найден.", "error")
        return redirect("/admin/products")

    photo_value = photo_file_id.strip()
    media_type_value = (media_type or existing.media_type or "photo").strip().lower()
    if media_type_value not in {"photo", "video", "animation", "document", "none"}:
        media_type_value = "photo"

    if no_media is not None:
        photo_value = ""
        media_type_value = "none"
    if photo_upload and photo_upload.filename:
        try:
            uploaded = await upload_media_to_telegram(photo_upload)
            if uploaded:
                media_type_value, photo_value = uploaded
        except Exception as exc:
            set_flash(request, f"Ошибка загрузки медиа: {exc}", "error")
            return redirect(f"/admin/products/{product_id}/edit")
    if not photo_value and media_type_value != "none":
        photo_value = existing.photo_file_id
        media_type_value = (existing.media_type or "photo").strip().lower()

    await repo.update_product(
        session,
        product_id,
        name=name.strip(),
        price_rub=int(price_rub),
        description=description.strip(),
        photo_file_id=photo_value,
        media_type=media_type_value,
        content=content.strip(),
        is_active=is_active is not None,
    )
    set_flash(request, "Товар обновлен.", "success")
    return redirect("/admin/products")


@app.post("/admin/products/{product_id}/toggle")
async def product_toggle(
    request: Request,
    product_id: int,
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    if not is_logged_in(request):
        return redirect("/admin/login")

    product = await repo.get_product(session, product_id)
    if not product:
        set_flash(request, "Товар не найден.", "error")
        return redirect("/admin/products")

    await repo.update_product(session, product_id, is_active=not product.is_active)
    set_flash(request, "Статус товара изменен.", "success")
    return redirect("/admin/products")


@app.post("/admin/products/{product_id}/cancel")
async def product_cancel(
    request: Request,
    product_id: int,
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    if not is_logged_in(request):
        return redirect("/admin/login")

    product = await repo.get_product(session, product_id)
    if not product:
        set_flash(request, "Товар не найден.", "error")
        return redirect("/admin/products")

    if not product.is_active:
        set_flash(request, "Товар уже снят с продажи.", "info")
        return redirect("/admin/products")

    await repo.update_product(session, product_id, is_active=False)
    set_flash(request, "Товар снят с продажи.", "success")
    return redirect("/admin/products")


@app.post("/admin/products/{product_id}/delete")
async def product_delete(
    request: Request,
    product_id: int,
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    if not is_logged_in(request):
        return redirect("/admin/login")

    result = await repo.delete_product(session, product_id)
    if result == "deleted":
        set_flash(request, "Товар удален.", "success")
    else:
        set_flash(request, "По товару есть заказы. Он деактивирован.", "info")
    return redirect("/admin/products")


@app.get("/admin/settings", response_class=HTMLResponse)
async def settings_page(request: Request, session: AsyncSession = Depends(get_session)):
    if not is_logged_in(request):
        return redirect("/admin/login")

    data = {
        "intro": await repo.get_setting(session, repo.SETTING_INTRO, default=""),
        "intro_photo": await repo.get_setting(session, repo.SETTING_INTRO_PHOTO, default=""),
        "intro_media_type": await repo.get_setting(session, repo.SETTING_INTRO_MEDIA_TYPE, default="none"),
        "crypto_enabled": await repo.get_setting(session, repo.SETTING_CRYPTO_ENABLED, default="1"),
        "card_enabled": await repo.get_setting(session, repo.SETTING_MANUAL_ENABLED, default="1"),
        "ozon_enabled": await repo.get_setting(session, repo.SETTING_OZON_ENABLED, default="0"),
        "yandex_enabled": await repo.get_setting(session, repo.SETTING_YANDEX_ENABLED, default="0"),
        "yoomoney_enabled": await repo.get_setting(session, repo.SETTING_YOOMONEY_ENABLED, default="0"),
        "manual_instructions": await repo.get_setting(
            session,
            repo.SETTING_MANUAL_INSTRUCTIONS,
            default=settings.manual_payment_instructions_default,
        ),
        "ozon_instructions": await repo.get_setting(
            session,
            repo.SETTING_OZON_INSTRUCTIONS,
            default="Оплатите через Озон Банк и пришлите чек.",
        ),
        "yandex_instructions": await repo.get_setting(
            session,
            repo.SETTING_YANDEX_INSTRUCTIONS,
            default="Оплатите через Яндекс Банк и пришлите чек.",
        ),
        "yoomoney_instructions": await repo.get_setting(
            session,
            repo.SETTING_YOOMONEY_INSTRUCTIONS,
            default="Оплатите через ЮMoney и пришлите чек.",
        ),
        "btn_catalog": await repo.get_setting(session, repo.SETTING_BTN_CATALOG, default="💎Товары"),
        "btn_proofs": await repo.get_setting(session, repo.SETTING_BTN_PROOFS, default="✅ Доказательства"),
        "btn_support": await repo.get_setting(session, repo.SETTING_BTN_SUPPORT, default="🛠 Техподдержка"),
        "btn_admin": await repo.get_setting(session, repo.SETTING_BTN_ADMIN, default="⚙️Админка"),
        "btn_buy": await repo.get_setting(session, repo.SETTING_BTN_BUY, default="Купить"),
        "btn_back": await repo.get_setting(session, repo.SETTING_BTN_BACK, default="Назад"),
        "btn_pay_crypto": await repo.get_setting(session, repo.SETTING_BTN_PAY_CRYPTO, default="CryptoBot"),
        "btn_pay_card": await repo.get_setting(session, repo.SETTING_BTN_PAY_CARD, default="Перевод/Карта"),
        "btn_pay_ozon": await repo.get_setting(session, repo.SETTING_BTN_PAY_OZON, default="Озон Банк"),
        "btn_pay_yandex": await repo.get_setting(session, repo.SETTING_BTN_PAY_YANDEX, default="Яндекс Банк"),
        "btn_pay_yoomoney": await repo.get_setting(session, repo.SETTING_BTN_PAY_YOOMONEY, default="ЮMoney"),
        "btn_i_paid": await repo.get_setting(session, repo.SETTING_BTN_I_PAID, default="Я оплатил"),
        "btn_cancel_order": await repo.get_setting(session, repo.SETTING_BTN_CANCEL_ORDER, default="Отменить"),
        "support_contact": await repo.get_setting(session, repo.SETTING_SUPPORT_CONTACT, default="@support"),
        "proofs_text": await repo.get_setting(
            session,
            repo.SETTING_PROOFS_TEXT,
            default="Добавьте сюда ваши доказательства/отзывы.",
        ),
        "proofs_enabled": await repo.get_setting(session, repo.SETTING_PROOFS_ENABLED, default="1"),
    }
    return render(request, "settings.html", data)


@app.post("/admin/settings")
async def settings_save(
    request: Request,
    session: AsyncSession = Depends(get_session),
    intro: str = Form(""),
    intro_photo: str = Form(""),
    intro_media_type: str = Form("none"),
    intro_no_media: str | None = Form(None),
    intro_photo_upload: UploadFile | None = File(default=None),
    crypto_enabled: str | None = Form(None),
    card_enabled: str | None = Form(None),
    ozon_enabled: str | None = Form(None),
    yandex_enabled: str | None = Form(None),
    yoomoney_enabled: str | None = Form(None),
    manual_instructions: str = Form(""),
    ozon_instructions: str = Form(""),
    yandex_instructions: str = Form(""),
    yoomoney_instructions: str = Form(""),
    btn_catalog: str = Form("💎Товары"),
    btn_proofs: str = Form("✅ Доказательства"),
    btn_support: str = Form("🛠 Техподдержка"),
    btn_admin: str = Form("⚙️Админка"),
    btn_buy: str = Form("Купить"),
    btn_back: str = Form("Назад"),
    btn_pay_crypto: str = Form("CryptoBot"),
    btn_pay_card: str = Form("Перевод/Карта"),
    btn_pay_ozon: str = Form("Озон Банк"),
    btn_pay_yandex: str = Form("Яндекс Банк"),
    btn_pay_yoomoney: str = Form("ЮMoney"),
    btn_i_paid: str = Form("Я оплатил"),
    btn_cancel_order: str = Form("Отменить"),
    support_contact: str = Form("@support"),
    proofs_text: str = Form(""),
    proofs_enabled: str | None = Form(None),
) -> RedirectResponse:
    if not is_logged_in(request):
        return redirect("/admin/login")

    intro_photo_value = intro_photo.strip()
    intro_media_type_value = (intro_media_type or "none").strip().lower()
    if intro_media_type_value not in {"photo", "video", "animation", "document", "none"}:
        intro_media_type_value = "none"
    if intro_no_media is not None:
        intro_photo_value = ""
        intro_media_type_value = "none"
    if intro_photo_upload and intro_photo_upload.filename:
        try:
            uploaded = await upload_media_to_telegram(intro_photo_upload)
            if uploaded:
                intro_media_type_value, intro_photo_value = uploaded
        except Exception as exc:
            set_flash(request, f"Ошибка загрузки медиа вступления: {exc}", "error")
            return redirect("/admin/settings")

    await repo.set_setting(session, repo.SETTING_INTRO, intro)
    await repo.set_setting(session, repo.SETTING_INTRO_PHOTO, intro_photo_value)
    await repo.set_setting(session, repo.SETTING_INTRO_MEDIA_TYPE, intro_media_type_value)
    await repo.set_setting(session, repo.SETTING_CRYPTO_ENABLED, "1" if crypto_enabled else "0")
    await repo.set_setting(session, repo.SETTING_MANUAL_ENABLED, "1" if card_enabled else "0")
    await repo.set_setting(session, repo.SETTING_OZON_ENABLED, "1" if ozon_enabled else "0")
    await repo.set_setting(session, repo.SETTING_YANDEX_ENABLED, "1" if yandex_enabled else "0")
    await repo.set_setting(session, repo.SETTING_YOOMONEY_ENABLED, "1" if yoomoney_enabled else "0")
    await repo.set_setting(session, repo.SETTING_MANUAL_INSTRUCTIONS, manual_instructions)
    await repo.set_setting(session, repo.SETTING_OZON_INSTRUCTIONS, ozon_instructions)
    await repo.set_setting(session, repo.SETTING_YANDEX_INSTRUCTIONS, yandex_instructions)
    await repo.set_setting(session, repo.SETTING_YOOMONEY_INSTRUCTIONS, yoomoney_instructions)
    await repo.set_setting(session, repo.SETTING_BTN_CATALOG, btn_catalog.strip() or "💎Товары")
    await repo.set_setting(session, repo.SETTING_BTN_PROOFS, btn_proofs.strip() or "✅ Доказательства")
    await repo.set_setting(session, repo.SETTING_BTN_SUPPORT, btn_support.strip() or "🛠 Техподдержка")
    await repo.set_setting(session, repo.SETTING_BTN_ADMIN, btn_admin.strip() or "⚙️Админка")
    await repo.set_setting(session, repo.SETTING_BTN_BUY, btn_buy.strip() or "Купить")
    await repo.set_setting(session, repo.SETTING_BTN_BACK, btn_back.strip() or "Назад")
    await repo.set_setting(session, repo.SETTING_BTN_PAY_CRYPTO, btn_pay_crypto.strip() or "CryptoBot")
    await repo.set_setting(session, repo.SETTING_BTN_PAY_CARD, btn_pay_card.strip() or "Перевод/Карта")
    await repo.set_setting(session, repo.SETTING_BTN_PAY_OZON, btn_pay_ozon.strip() or "Озон Банк")
    await repo.set_setting(session, repo.SETTING_BTN_PAY_YANDEX, btn_pay_yandex.strip() or "Яндекс Банк")
    await repo.set_setting(session, repo.SETTING_BTN_PAY_YOOMONEY, btn_pay_yoomoney.strip() or "ЮMoney")
    await repo.set_setting(session, repo.SETTING_BTN_I_PAID, btn_i_paid.strip() or "Я оплатил")
    await repo.set_setting(session, repo.SETTING_BTN_CANCEL_ORDER, btn_cancel_order.strip() or "Отменить")
    await repo.set_setting(session, repo.SETTING_SUPPORT_CONTACT, support_contact.strip())
    await repo.set_setting(session, repo.SETTING_PROOFS_ENABLED, "1" if proofs_enabled else "0")
    await repo.set_setting(
        session,
        repo.SETTING_PROOFS_TEXT,
        (proofs_text or "").strip() or "Доказательства пока не добавлены.",
    )
    set_flash(request, "Настройки сохранены.", "success")
    return redirect("/admin/settings")


@app.get("/admin/broadcast", response_class=HTMLResponse)
async def broadcast_page(request: Request):
    if not is_logged_in(request):
        return redirect("/admin/login")
    return render(request, "broadcast.html", {})


@app.post("/admin/broadcast")
async def broadcast_send(
    request: Request,
    session: AsyncSession = Depends(get_session),
    text: str = Form(""),
    media_upload: UploadFile | None = File(default=None),
) -> RedirectResponse:
    if not is_logged_in(request):
        return redirect("/admin/login")
    if not text.strip() and not (media_upload and media_upload.filename):
        set_flash(request, "Добавьте текст и/или файл для рассылки.", "error")
        return redirect("/admin/broadcast")

    media_file_id: str | None = None
    media_type: str | None = None
    if media_upload and media_upload.filename:
        try:
            uploaded = await upload_media_to_telegram(media_upload)
            if uploaded:
                media_type, media_file_id = uploaded
        except Exception as exc:
            set_flash(request, f"Ошибка загрузки файла: {exc}", "error")
            return redirect("/admin/broadcast")

    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    try:
        success, failed = await broadcast_message(
            bot,
            session,
            text.strip(),
            media_file_id=media_file_id,
            media_type=media_type,
        )
    finally:
        await bot.session.close()

    set_flash(request, f"Рассылка завершена. Успешно: {success}, ошибок: {failed}.", "success")
    return redirect("/admin/broadcast")


@app.post("/admin/stats/reset")
async def reset_stats(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    if not is_logged_in(request):
        return redirect("/admin/login")

    await repo.reset_analytics_period(session)
    set_flash(request, "Статистика сброшена. Новый период начат.", "success")
    return redirect("/admin")


@app.post("/admin/events/clear")
async def clear_events(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    if not is_logged_in(request):
        return redirect("/admin/login")

    deleted = await repo.clear_events(session)
    set_flash(request, f"События очищены. Удалено: {deleted}.", "success")
    return redirect("/admin")


@app.get("/admin/orders", response_class=HTMLResponse)
async def orders_page(request: Request, session: AsyncSession = Depends(get_session)):
    if not is_logged_in(request):
        return redirect("/admin/login")

    orders = await repo.list_orders(session, limit=300)
    products = {p.id: p for p in await repo.list_products(session, active_only=False)}
    return render(request, "orders.html", {"orders": orders, "products": products})


@app.post("/admin/orders/clear")
async def clear_orders(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    if not is_logged_in(request):
        return redirect("/admin/login")

    deleted = await repo.clear_orders(session)
    set_flash(request, f"Список заказов очищен. Удалено: {deleted}.", "success")
    return redirect("/admin/orders")


@app.post("/admin/orders/{order_id}/delete")
async def delete_order(
    request: Request,
    order_id: int,
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    if not is_logged_in(request):
        return redirect("/admin/login")

    deleted = await repo.delete_order(session, order_id)
    if deleted:
        set_flash(request, f"Заказ #{order_id} удален.", "success")
    else:
        set_flash(request, f"Заказ #{order_id} не найден.", "error")
    return redirect("/admin/orders")


@app.post("/admin/orders/{order_id}/confirm")
async def confirm_order(
    request: Request,
    order_id: int,
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    if not is_logged_in(request):
        return redirect("/admin/login")

    order = await repo.get_order(session, order_id)
    if not order:
        set_flash(request, "Заказ не найден.", "error")
        return redirect("/admin/orders")

    await repo.mark_order_status(session, order_id, OrderStatus.paid)
    await repo.log_event(
        session,
        "purchase_paid_admin_web",
        user_id=order.user_id,
        payload={"order_id": order_id},
    )

    item = await repo.get_order_with_product(session, order_id)
    if item:
        _, product = item
        bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        try:
            await bot.send_message(
                order.user_id,
                "Оплата подтверждена! Ваш товар:\n" + format_text(product.content),
                parse_mode="HTML",
            )
            set_flash(request, f"Заказ #{order_id} подтвержден и товар отправлен.", "success")
        except TelegramAPIError:
            set_flash(request, f"Заказ #{order_id} подтвержден, но отправка пользователю не удалась.", "error")
        finally:
            await bot.session.close()
    else:
        set_flash(request, f"Заказ #{order_id} подтвержден.", "success")

    return redirect("/admin/orders")
