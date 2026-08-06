import httpx
from bot.config import get_settings

CRYPTOBOT_API = "https://pay.crypt.bot/api"


async def create_invoice(amount_rub: float, payment_id: int, description: str) -> str:
    s = get_settings()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{CRYPTOBOT_API}/createInvoice",
            headers={"Crypto-Pay-API-Token": s.CRYPTOBOT_TOKEN},
            json={
                "currency_type": "fiat",
                "fiat": "RUB",
                "amount": str(amount_rub),
                "description": description,
                "payload": f"payment_id:{payment_id}",
                "paid_btn_name": "callback",
                "paid_btn_url": f"https://t.me/{s.BOT_USERNAME}",
            },
        )
        resp.raise_for_status()
        return resp.json()["result"]["bot_invoice_url"]
