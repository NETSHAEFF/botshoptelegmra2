from __future__ import annotations

from typing import List

from pydantic import Field, field_validator, AliasChoices
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Project configuration loaded from environment variables.

    All sensitive data must be provided via .env (see .env.example).
    """

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    bot_token: str = Field(
        validation_alias=AliasChoices("BOT_TOKEN", "bot_token", "\ufeffBOT_TOKEN")
    )
    admin_ids: List[int] = Field(validation_alias=AliasChoices("ADMIN_IDS", "admin_ids"))

    database_url: str = Field(
        default="sqlite+aiosqlite:///./bot.db",
        alias="DATABASE_URL",
    )

    cryptopay_api_token: str = Field(alias="CRYPTOPAY_API_TOKEN")
    cryptopay_testnet: bool = Field(default=False, alias="CRYPTOPAY_TESTNET")
    cryptopay_api_url: str = Field(
        default="https://pay.crypt.bot/api",
        alias="CRYPTOPAY_API_URL",
    )
    crypto_fiat_currency: str = Field(default="RUB", alias="CRYPTO_FIAT_CURRENCY")
    crypto_check_interval: int = Field(default=30, alias="CRYPTO_CHECK_INTERVAL")

    intro_default: str = Field(
        default="Добро пожаловать в наш магазин!",
        alias="INTRO_DEFAULT",
    )
    crypto_payment_enabled_default: bool = Field(
        default=True,
        alias="CRYPTO_PAYMENT_ENABLED_DEFAULT",
    )
    stars_payment_enabled_default: bool = Field(
        default=True,
        alias="STARS_PAYMENT_ENABLED_DEFAULT",
    )
    stars_rub_rate: float = Field(
        default=1.7,
        alias="STARS_RUB_RATE",
    )
    manual_payment_enabled_default: bool = Field(
        default=True,
        alias="MANUAL_PAYMENT_ENABLED_DEFAULT",
    )
    manual_payment_instructions_default: str = Field(
        default=(
            "Оплатите по реквизитам:\n"
            "Карта 0000 0000 0000 0000\n"
            "Получатель: ИП Иванов\n"
            "Сумма: укажите сумму заказа.\n"
            "После оплаты нажмите «Я оплатил» и пришлите чек."
        ),
        alias="MANUAL_PAYMENT_INSTRUCTIONS_DEFAULT",
    )

    web_admin_username: str = Field(default="admin", alias="WEB_ADMIN_USERNAME")
    web_admin_password: str = Field(default="change_me", alias="WEB_ADMIN_PASSWORD")
    web_admin_secret: str = Field(default="change-this-secret", alias="WEB_ADMIN_SECRET")
    web_admin_host: str = Field(default="127.0.0.1", alias="WEB_ADMIN_HOST")
    web_admin_port: int = Field(default=8080, alias="WEB_ADMIN_PORT")

    @field_validator("admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, value):
        if isinstance(value, int):
            return [value]
        if isinstance(value, str):
            return [int(x.strip()) for x in value.split(",") if x.strip()]
        return value

    @property
    def cryptopay_base_url(self) -> str:
        """Resolve base URL for CryptoBot API (testnet or mainnet)."""

        if self.cryptopay_testnet:
            return "https://testnet-pay.crypt.bot/api"
        return self.cryptopay_api_url.rstrip("/")


def load_settings() -> Settings:
    return Settings()
