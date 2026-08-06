import hashlib
from bot.config import get_settings

FREEKASSA_FORM_URL = "https://pay.freekassa.ru/"


def create_payment_url(amount_rub: float, payment_id: int) -> str:
    s = get_settings()
    amount_str = f"{amount_rub:.2f}"
    sign = hashlib.md5(
        f"{s.FREEKASSA_SHOP_ID}:{amount_str}:{s.FREEKASSA_SECRET1}:RUB:{payment_id}".encode()
    ).hexdigest()
    return (
        f"{FREEKASSA_FORM_URL}?m={s.FREEKASSA_SHOP_ID}"
        f"&oa={amount_str}&currency=RUB&o={payment_id}&s={sign}&lang=ru"
        f"&success_url=https://t.me/{s.BOT_USERNAME}"
        f"&failure_url=https://t.me/{s.BOT_USERNAME}"
    )


def verify_signature(merchant_id: str, amount: str, order_id: str, sign: str) -> bool:
    s = get_settings()
    expected = hashlib.md5(
        f"{merchant_id}:{amount}:{s.FREEKASSA_SECRET2}:{order_id}".encode()
    ).hexdigest()
    return expected == sign
