from decimal import Decimal

from fastapi import APIRouter, Request

from bot.services.yookassa import get_payment_status
from bot.services.balance import credit_topup

router = APIRouter()


@router.post("/webhook/yookassa")
async def yookassa_webhook(request: Request):
    data = await request.json()
    if data.get("event") != "payment.succeeded":
        return {"ok": True}

    yookassa_payment_id = data.get("object", {}).get("id")
    if not yookassa_payment_id:
        return {"ok": True}

    status_data = await get_payment_status(yookassa_payment_id)
    if status_data.get("status") != "succeeded":
        return {"ok": True}

    payment_id = status_data.get("metadata", {}).get("payment_id")
    if not payment_id:
        return {"ok": True}

    amount = Decimal(status_data["amount"]["value"])
    async with request.app.state.session_factory() as session:
        await credit_topup(int(payment_id), amount, yookassa_payment_id, session)
    return {"ok": True}
