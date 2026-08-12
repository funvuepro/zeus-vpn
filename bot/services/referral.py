import logging
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Payment, PaymentStatus, User

REFERRAL_BONUS_RUB = Decimal("100.00")


async def notify_user(telegram_id: int, text: str):
    pass  # reassigned at startup in main.py


async def get_referral_registered_count(user_id: int, session: AsyncSession) -> int:
    result = await session.execute(
        select(func.count(User.id)).where(User.referred_by == user_id)
    )
    return result.scalar_one_or_none() or 0


async def get_referral_paid_count(user_id: int, session: AsyncSession) -> int:
    paid_user_ids = select(Payment.user_id).where(Payment.status == PaymentStatus.paid).distinct()
    result = await session.execute(
        select(func.count(User.id)).where(
            User.referred_by == user_id,
            User.id.in_(paid_user_ids),
        )
    )
    return result.scalar_one_or_none() or 0


async def grant_referral_bonus(user: User, session: AsyncSession) -> None:
    if not user.referred_by or user.referral_bonus_granted:
        return

    paid_count = await session.scalar(
        select(func.count(Payment.id)).where(
            Payment.user_id == user.id,
            Payment.status == PaymentStatus.paid,
        )
    )
    if (paid_count or 0) != 1:
        return  # not the user's first paid payment

    referrer = await session.get(User, user.referred_by)
    if referrer is None:
        return

    from bot.services.balance import reactivate_access  # deferred: balance imports this module

    referrer.balance += REFERRAL_BONUS_RUB
    try:
        await reactivate_access(referrer, session)
    except Exception as e:
        # This runs after credit_topup's own commit, so a Remnawave hiccup here
        # must not prevent the bonus itself from committing — otherwise the
        # payment is already flipped to paid (idempotency check blocks retries)
        # and the referral bonus would be lost permanently, not just delayed.
        logging.warning(f"Remnawave reactivation failed for referrer {referrer.telegram_id}: {e}")
    user.referral_bonus_granted = True
    await session.commit()
    await notify_user(referrer.telegram_id, f"⚡ +{REFERRAL_BONUS_RUB} ₽ на баланс за приглашённого друга!")
