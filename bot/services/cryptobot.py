from __future__ import annotations

from typing import Any

import aiohttp


class CryptoBotError(RuntimeError):
    pass


class CryptoBotClient:
    def __init__(self, api_token: str, base_url: str, session: aiohttp.ClientSession) -> None:
        self._api_token = api_token
        self._base_url = base_url.rstrip("/")
        self._session = session

    async def _request(self, method: str, endpoint: str, payload: dict | None = None) -> dict[str, Any]:
        url = f"{self._base_url}/{endpoint.lstrip('/')}"
        headers = {
            "Crypto-Pay-API-Token": self._api_token,
            "Content-Type": "application/json",
        }

        async with self._session.request(method, url, json=payload, headers=headers) as response:
            data = await response.json(content_type=None)

        if not data.get("ok"):
            raise CryptoBotError(f"CryptoBot API error: {data}")
        return data["result"]

    async def create_invoice(
        self,
        amount: int,
        fiat_currency: str,
        description: str,
        payload: str,
    ) -> dict[str, Any]:
        # We use fiat pricing (RUB) to match product prices in the catalog.
        body = {
            "amount": str(amount),
            "currency_type": "fiat",
            "fiat": fiat_currency,
            "description": description,
            "payload": payload,
        }
        return await self._request("POST", "createInvoice", payload=body)

    async def get_invoices(self, invoice_ids: list[str]) -> list[dict[str, Any]]:
        if not invoice_ids:
            return []

        body = {
            "invoice_ids": ",".join(invoice_ids),
        }
        result = await self._request("POST", "getInvoices", payload=body)
        return result.get("items", [])
