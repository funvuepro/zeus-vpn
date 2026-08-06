import hashlib
import hmac
import httpx
from bot.config import get_settings

LAVA_API = "https://api.lava.ru"


async def create_payment(amount_rub: float, payment_id: int, description: str) -> str:
    s = get_settings()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{LAVA_API}/business/invoice/create",
            headers={"Authorization": f"Bearer {s.LAVA_API_KEY}"},
            json={
                "shop_id": s.LAVA_SHOP_ID,
                "sum": amount_rub,
                "order_id": str(payment_id),
                "hook_url": f"{s.WEBHOOK_BASE_URL}/webhook/lava",
                "success_url": f"https://t.me/{s.BOT_USERNAME}",
                "fail_url": f"https://t.me/{s.BOT_USERNAME}",
                "expire": 3600,
                "comment": description,
            },
        )
        resp.raise_for_status()
        return resp.json()["data"]["url"]


def verify_lava_signature(data: dict, received_hash: str) -> bool:
    s = get_settings()
    sign_string = ":".join([
        str(data.get("order_id", "")),
        str(data.get("shop_id", "")),
        str(data.get("sum", "")),
        s.LAVA_API_KEY,
    ])
    expected = hashlib.sha256(sign_string.encode()).hexdigest()
    return hmac.compare_digest(expected, received_hash)
