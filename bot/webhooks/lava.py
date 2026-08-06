from fastapi import APIRouter, HTTPException, Request

from bot.services.lava import verify_lava_signature
from bot.services.subscription import activate_subscription

router = APIRouter()


@router.post("/webhook/lava")
async def lava_webhook(request: Request):
    data = await request.json()

    received_hash = data.get("hash", "")
    if not verify_lava_signature(data, received_hash):
        raise HTTPException(status_code=400, detail="Invalid signature")

    if data.get("status") != "success":
        return {"ok": True}

    payment_id = int(data["order_id"])
    async with request.app.state.session_factory() as session:
        await activate_subscription(payment_id, session)
    return {"ok": True}
