from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import AppSettings, Payment, PaymentStatus, User
from bot.services.remnawave import remnawave
from bot.services.referral import grant_referral_bonus

DEFAULT_DAILY_RATE = Decimal("1.00")


async def notify_user(telegram_id: int, text: str):
    pass  # reassigned at startup in main.py


def calculate_daily_charge(daily_rate_per_device: Decimal, devices_limit: int) -> Decimal:
    multiplier = Decimal("0.5") * (Decimal(devices_limit) + 1)
    return (daily_rate_per_device * multiplier).quantize(Decimal("0.01"))


async def get_daily_rate_per_device(session: AsyncSession) -> Decimal:
    row = await session.get(AppSettings, 1)
    return row.daily_rate_per_device if row else DEFAULT_DAILY_RATE


async def set_daily_rate_per_device(session: AsyncSession, value: Decimal) -> None:
    row = await session.get(AppSettings, 1)
    if row is None:
        session.add(AppSettings(id=1, daily_rate_per_device=value))
    else:
        row.daily_rate_per_device = value
    await session.commit()


async def reactivate_access(user: User, session: AsyncSession) -> None:
    """Clear grace period and re-enable access after the balance is topped up.

    Must be called by every code path that credits balance (payments, promo
    codes) — run_daily_billing only processes users with access_active == True,
    so a disabled user who is never reactivated stays excluded forever.
    Does not commit; the caller owns the transaction.
    """
    if user.grace_started_at is not None:
        user.grace_started_at = None
    if not user.access_active:
        user.access_active = True
        if user.remnawave_uuid:
            await remnawave.enable_user(user.remnawave_uuid)


async def credit_topup(payment_id: int, amount: Decimal, external_id: str, session: AsyncSession) -> None:
    result = await session.execute(
        update(Payment)
        .where(Payment.id == payment_id, Payment.status == PaymentStatus.pending)
        .values(status=PaymentStatus.paid, external_id=external_id)
        .returning(Payment)
    )
    payment = result.scalar_one_or_none()
    if payment is None:
        return  # already credited or unknown payment id

    user = await session.get(User, payment.user_id)
    user.balance += amount

    await reactivate_access(user, session)

    await session.commit()
    await notify_user(user.telegram_id, f"⚡ Баланс пополнен на {amount} ₽. Текущий баланс: {user.balance} ₽")
    await grant_referral_bonus(user, session)
