"""HTTP-клиент бота для общения с API-сервисом.

Бот не ходит в БД напрямую (кроме легаси-логики, до полной миграции).
Деловые операции — через REST API.
"""

import logging
from typing import Any

import httpx

from shared.config import get_settings

logger = logging.getLogger(__name__)
_settings = get_settings()


class ApiClient:
    """Асинхронный клиент к src_fastapi."""

    def __init__(self, base_url: str | None = None, bot_token: str | None = None):
        self._base_url = (base_url or _settings.WEBAPP_BASE_URL).rstrip("/")
        self._token = bot_token or _settings.TOKEN

    async def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        json_body: dict | None = None,
        init_data: str | None = None,
    ) -> dict[str, Any] | None:
        url = f"{self._base_url}{path}"
        headers = {"Content-Type": "application/json"}
        if init_data:
            headers["Authorization"] = init_data
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.request(
                    method, url, params=params, json=json_body, headers=headers
                )
                if resp.status_code >= 400:
                    logger.warning("API %s %s -> %s %s", method, url, resp.status_code, resp.text)
                    return None
                return resp.json()
            except Exception:
                logger.exception("Ошибка запроса к API %s %s", method, url)
                return None

    # --- Игры ---
    async def create_game_room(
        self, init_data: str, game_type: str, chat_id: int, target_id: int | None = None, bet: int = 0
    ) -> dict | None:
        return await self._request(
            "POST",
            "/api/games/rooms",
            json_body={
                "game_type": game_type,
                "chat_id": chat_id,
                "target_id": target_id,
                "bet": bet,
            },
            init_data=init_data,
        )

    async def get_game_room(self, room_id: str, init_data: str) -> dict | None:
        return await self._request("GET", f"/api/games/rooms/{room_id}", init_data=init_data)

    async def join_game_room(self, room_id: str, init_data: str) -> dict | None:
        return await self._request("POST", f"/api/games/rooms/{room_id}/join", init_data=init_data)

    async def game_action(self, room_id: str, init_data: str, action: dict) -> dict | None:
        return await self._request(
            "POST", f"/api/games/rooms/{room_id}/action", json_body=action, init_data=init_data
        )

    async def cancel_game_room(self, room_id: str, init_data: str) -> dict | None:
        return await self._request("POST", f"/api/games/rooms/{room_id}/cancel", init_data=init_data)

    # --- Реклама ---
    async def submit_ad_campaign(self, init_data: str, data: dict) -> dict | None:
        return await self._request(
            "POST", "/api/ads/campaigns", json_body=data, init_data=init_data
        )

    async def list_ad_campaigns(self, init_data: str, status: str | None = None) -> list | None:
        params = {"status": status} if status else None
        result = await self._request("GET", "/api/ads/campaigns", params=params, init_data=init_data)
        return result if isinstance(result, list) else None

    # --- Платежи ---
    async def create_payment(self, init_data: str, payment_type: str, amount: int, meta: dict) -> dict | None:
        return await self._request(
            "POST",
            "/api/payments/init",
            json_body={"payment_type": payment_type, "amount": amount, "meta": meta},
            init_data=init_data,
        )
