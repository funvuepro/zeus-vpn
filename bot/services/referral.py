from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database.models import (
    Payment,
    PaymentStatus,
    ReferralStatus,
    ReferralTransaction,
    User,
    Withdrawal,
    WithdrawalProvider,
    WithdrawalStatus,
    CryptoType,
)


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


async def get_referral_balance(user_id: int, session: AsyncSession) -> Decimal:
    result = await session.execute(
        select(func.sum(ReferralTransaction.amount)).where(
            ReferralTransaction.referrer_id == user_id,
            ReferralTransaction.status == ReferralStatus.pending,
        )
    )
    return result.scalar_one_or_none() or Decimal("0.00")


async def request_withdrawal(
    user_id: int,
    amount: Decimal,
    provider: WithdrawalProvider,
    wallet_address: str,
    session: AsyncSession,
    crypto_type: CryptoType | None = None,
) -> Withdrawal:
    if amount < Decimal(str(settings.MIN_WITHDRAWAL_RUB)):
        raise ValueError(f"Минимальная сумма вывода: {int(settings.MIN_WITHDRAWAL_RUB)} ₽")

    balance = await get_referral_balance(user_id, session)
    if amount > balance:
        raise ValueError(f"Недостаточно средств. Доступно: {balance} ₽")

    result = await session.execute(
        select(ReferralTransaction).where(
            ReferralTransaction.referrer_id == user_id,
            ReferralTransaction.status == ReferralStatus.pending,
        )
    )
    txs = result.scalars().all()

    spent = Decimal("0.00")
    for tx in txs:
        if spent >= amount:
            break
        tx.status = ReferralStatus.withdrawn
        spent += tx.amount

    withdrawal = Withdrawal(
        user_id=user_id,
        amount=amount,
        provider=provider,
        wallet_address=wallet_address,
        crypto_type=crypto_type,
        status=WithdrawalStatus.pending,
    )
    session.add(withdrawal)
    await session.commit()
    return withdrawal
