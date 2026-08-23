import asyncio
from datetime import datetime, timezone, timedelta
from typing import Tuple

import httpx


class RemnaWaveClient:
    def __init__(self, base_url: str, api_token: str, default_squad_uuid: str = ""):
        self._base_url = base_url.rstrip("/")
        self._api_token = api_token
        self._default_squad_uuid = default_squad_uuid
        self._http: httpx.AsyncClient | None = None
        self._lock: asyncio.Lock | None = None

    def _get_http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(
                timeout=10.0,
                headers={
                    "Authorization": f"Bearer {self._api_token}",
                    "X-Forwarded-Proto": "https",
                    "X-Forwarded-For": "127.0.0.1",
                },
            )
        return self._http

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def _request(self, method: str, path: str, **kwargs):
        resp = await self._get_http().request(
            method, f"{self._base_url}/api{path}", **kwargs
        )
        resp.raise_for_status()
        return resp

    @staticmethod
    def _iso(dt: datetime) -> str:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def _expire_iso(days: int) -> str:
        return RemnaWaveClient._iso(
            datetime.now(timezone.utc) + timedelta(days=days)
        )

    async def create_user(self, username: str, expire_days: int) -> Tuple[str, str]:
        """Create VPN user. Returns (subscription_url, remnawave_id).

        Remnawave's user objects carry no "uuid" field — actions/deletion
        endpoints key off the numeric "id" instead, so that's what gets
        stored (as a string) in User.remnawave_uuid despite the column name.
        """
        payload: dict = {
            "username": username,
            "expireAt": self._expire_iso(expire_days),
            "status": "ACTIVE",
            "trafficLimitStrategy": "NO_RESET",
        }
        if username.startswith("user_") and username[5:].isdigit():
            payload["telegramId"] = int(username[5:])
        if self._default_squad_uuid:
            payload["activeInternalSquads"] = [self._default_squad_uuid]
        resp = await self._request("POST", "/users", json=payload)
        data = resp.json()["response"]
        return data["subscriptionUrl"], str(data["id"])

    async def extend_user(self, username: str, expire_at: datetime) -> None:
        """Set user expiry to an absolute datetime."""
        await self._request(
            "PATCH",
            "/users",
            json={
                "username": username,
                "expireAt": self._iso(expire_at),
                "status": "ACTIVE",
            },
        )

    async def disable_user(self, uuid: str) -> None:
        await self._request("POST", f"/users/{uuid}/actions/disable")

    async def enable_user(self, uuid: str) -> None:
        await self._request("POST", f"/users/{uuid}/actions/enable")

    async def delete_user(self, uuid: str) -> None:
        await self._request("DELETE", f"/users/{uuid}")

    async def get_user_by_username(self, username: str) -> dict:
        """Returns full user dict from Remnawave: uuid, subscriptionUrl, status, expireAt, etc."""
        resp = await self._request("GET", f"/users/by-username/{username}")
        return resp.json()["response"]

    async def get_subscription_url(self, username: str) -> str:
        data = await self.get_user_by_username(username)
        return data["subscriptionUrl"]

    async def aclose(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None


class _LazyRemnaWaveProxy:
    _instance: RemnaWaveClient | None = None

    def _get(self) -> RemnaWaveClient:
        if self._instance is None:
            from bot.config import get_settings
            s = get_settings()
            self._instance = RemnaWaveClient(
                base_url=s.REMNAWAVE_URL,
                api_token=s.REMNAWAVE_API_TOKEN,
                default_squad_uuid=s.REMNAWAVE_DEFAULT_SQUAD_UUID,
            )
        return self._instance

    def __getattr__(self, name: str):
        return getattr(self._get(), name)


remnawave: RemnaWaveClient = _LazyRemnaWaveProxy()  # type: ignore[assignment]
