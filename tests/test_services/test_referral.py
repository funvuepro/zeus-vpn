import pytest
from decimal import Decimal
from bot.database.models import (
    Payment, Plan, PaymentProvider,
    ReferralTransaction, ReferralStatus,
    User, Withdrawal, WithdrawalProvider,
)
from bot.services.referral import get_referral_balance, request_withdrawal


async def test_get_referral_balance(db_session):
    user = User(telegram_id=300, username="ref_user")
    db_session.add(user)
    await db_session.commit()

    plan = Plan(name="Базовый", devices_limit=1, duration_days=30, price=Decimal("149.00"))
    db_session.add(plan)
    await db_session.commit()

    payer = User(telegram_id=301, username="payer_user", referred_by=user.id)
    db_session.add(payer)
    await db_session.commit()

    payment = Payment(
        user_id=payer.id, plan_id=plan.id,
        provider=PaymentProvider.cryptobot,
        amount=Decimal("149.00"),
    )
    db_session.add(payment)
    await db_session.commit()

    rt = ReferralTransaction(
        referrer_id=user.id,
        payment_id=payment.id,
        amount=Decimal("44.70"),
        status=ReferralStatus.pending,
    )
    db_session.add(rt)
    await db_session.commit()

    balance = await get_referral_balance(user.id, db_session)
    assert balance == Decimal("44.70")


async def test_withdrawal_requires_minimum(db_session):
    user = User(telegram_id=400, username="low_balance")
    db_session.add(user)
    await db_session.commit()

    with pytest.raises(ValueError, match="Минимальная сумма"):
        await request_withdrawal(
            user_id=user.id,
            amount=Decimal("50.00"),
            provider=WithdrawalProvider.cryptobot,
            wallet_address="UQtest",
            session=db_session,
        )
