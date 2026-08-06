import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse

import httpx


class MarzbanClient:
    def __init__(self, base_url: str, username: str, password: str):
        self._base_url = base_url.rstrip("/")
        self._username = username
        self._password = password
        self._token: str | None = None
        self._http: httpx.AsyncClient | None = None
        self._lock: asyncio.Lock | None = None

    def _get_http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=10.0)
        return self._http

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def _ensure_token(self):
        async with self._get_lock():
            if self._token:
                return
            await self._fetch_token()

    async def _fetch_token(self):
        resp = await self._get_http().post(
            f"{self._base_url}/api/admin/token",
            data={"username": self._username, "password": self._password},
        )
        resp.raise_for_status()
        self._token = resp.json()["access_token"]
        self._get_http().headers["Authorization"] = f"Bearer {self._token}"

    async def _request(self, method: str, path: str, **kwargs):
        await self._ensure_token()
        resp = await self._get_http().request(method, f"{self._base_url}{path}", **kwargs)
        if resp.status_code == 401:
            self._token = None
            await self._fetch_token()
            resp = await self._get_http().request(method, f"{self._base_url}{path}", **kwargs)
        resp.raise_for_status()
        return resp

    def _public_sub_url(self, marzban_url: str) -> str:
        from bot.config import get_settings
        host = get_settings().SUBSCRIPTION_HOST
        if not host:
            return marzban_url
        path = urlparse(marzban_url).path
        return host.rstrip("/") + path

    async def create_user(self, username: str, devices_limit: int, expire_days: int) -> str:
        expire_ts = int((datetime.now(timezone.utc) + timedelta(days=expire_days)).timestamp())
        resp = await self._request(
            "POST",
            "/api/user",
            json={
                "username": username,
                "proxies": {
                    "vless": {"id": str(uuid.uuid4()), "flow": "xtls-rprx-vision"}
                },
                "inbounds": {"vless": ["VLESS_REALITY"]},
                "expire": expire_ts,
                "data_limit": 0,
                "data_limit_reset_strategy": "no_reset",
                "status": "active",
            },
        )
        return self._public_sub_url(resp.json()["subscription_url"])

    async def extend_user(self, username: str, new_expire_days: int):
        expire_ts = int((datetime.now(timezone.utc) + timedelta(days=new_expire_days)).timestamp())
        await self._request(
            "PUT",
            f"/api/user/{username}",
            json={"expire": expire_ts, "status": "active"},
        )

    async def disable_user(self, username: str):
        await self._request("PUT", f"/api/user/{username}", json={"status": "disabled"})

    async def delete_user(self, username: str):
        await self._request("DELETE", f"/api/user/{username}")

    async def get_subscription_url(self, username: str) -> str:
        resp = await self._request("GET", f"/api/user/{username}")
        return self._public_sub_url(resp.json()["subscription_url"])

    async def aclose(self):
        if self._http is not None:
            await self._http.aclose()
            self._http = None


class _LazyMarzbanProxy:
    """Defers MarzbanClient creation until first use to avoid import-time settings loading."""

    _instance: MarzbanClient | None = None

    def _get(self) -> MarzbanClient:
        if self._instance is None:
            from bot.config import get_settings
            s = get_settings()
            self._instance = MarzbanClient(
                base_url=s.MARZBAN_URL,
                username=s.MARZBAN_USERNAME,
                password=s.MARZBAN_PASSWORD,
            )
        return self._instance

    def __getattr__(self, name: str):
        return getattr(self._get(), name)


marzban: MarzbanClient = _LazyMarzbanProxy()  # type: ignore[assignment]
