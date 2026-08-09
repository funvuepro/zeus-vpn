import uuid

import httpx

from bot.config import get_settings

YOOKASSA_API = "https://api.yookassa.ru/v3"


async def create_payment(amount_rub: float, payment_id: int, description: str) -> str:
    s = get_settings()
    idempotence_key = f"{payment_id}-{uuid.uuid4()}"
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{YOOKASSA_API}/payments",
            auth=(s.YOOKASSA_SHOP_ID, s.YOOKASSA_SECRET_KEY),
            headers={"Idempotence-Key": idempotence_key},
            json={
                "amount": {"value": f"{amount_rub:.2f}", "currency": "RUB"},
                "confirmation": {"type": "redirect", "return_url": f"https://t.me/{s.BOT_USERNAME}"},
                "capture": True,
                "description": description,
                "metadata": {"payment_id": str(payment_id)},
            },
        )
        resp.raise_for_status()
        return resp.json()["confirmation"]["confirmation_url"]


async def get_payment_status(yookassa_payment_id: str) -> dict:
    s = get_settings()
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{YOOKASSA_API}/payments/{yookassa_payment_id}",
            auth=(s.YOOKASSA_SHOP_ID, s.YOOKASSA_SECRET_KEY),
        )
        resp.raise_for_status()
        return resp.json()
