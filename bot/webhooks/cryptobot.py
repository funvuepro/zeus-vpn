import hashlib
import hmac
import json

from fastapi import APIRouter, HTTPException, Request

from bot.config import get_settings
from bot.services.subscription import activate_subscription

router = APIRouter()


@router.post("/webhook/cryptobot")
async def cryptobot_webhook(request: Request):
    s = get_settings()
    body = await request.body()
    signature = request.headers.get("crypto-pay-api-signature", "")
    secret = hashlib.sha256(s.CRYPTOBOT_TOKEN.encode()).digest()
    expected = hmac.new(secret, body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    data = json.loads(body)
    if data.get("update_type") != "invoice_paid":
        return {"ok": True}

    payload_obj = data.get("payload") or {}
    if not isinstance(payload_obj, dict):
        return {"ok": True}
    payload_str: str = payload_obj.get("payload", "")
    if not payload_str.startswith("payment_id:"):
        return {"ok": True}

    payment_id = int(payload_str.split(":")[1])
    async with request.app.state.session_factory() as session:
        await activate_subscription(payment_id, session)
    return {"ok": True}
