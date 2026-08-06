from fastapi import APIRouter, Request
from bot.services.freekassa import verify_signature
from bot.services.subscription import activate_subscription

router = APIRouter()


@router.post("/webhook/freekassa")
async def freekassa_webhook(request: Request):
    form = await request.form()
    merchant_id = form.get("MERCHANT_ID", "")
    amount = form.get("AMOUNT", "")
    order_id = form.get("MERCHANT_ORDER_ID", "")
    sign = form.get("SIGN", "")

    if not verify_signature(merchant_id, amount, order_id, sign):
        return "bad sign"

    async with request.app.state.session_factory() as session:
        await activate_subscription(int(order_id), session)
    return "YES"
