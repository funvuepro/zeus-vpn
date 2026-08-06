import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from bot.database.models import (
    Payment, Plan, Subscription, User,
    PaymentProvider, PaymentStatus, SubscriptionStatus,
)
from bot.services.subscription import activate_subscription


async def test_activate_creates_subscription(db_session):
    user = User(telegram_id=100, username="u1")
    plan = Plan(name="Стандарт", devices_limit=3, duration_days=30, price=Decimal("249.00"))
    db_session.add_all([user, plan])
    await db_session.commit()

    payment = Payment(
        user_id=user.id, plan_id=plan.id,
        provider=PaymentProvider.cryptobot,
        external_id="inv_1",
        amount=Decimal("249.00"),
    )
    db_session.add(payment)
    await db_session.commit()

    with patch("bot.services.subscription.remnawave") as mock_remnawave:
        mock_remnawave.create_user = AsyncMock(return_value=("https://vpn.com/sub/abc", "uuid-123"))
        with patch("bot.services.subscription.notify_user", new_callable=AsyncMock):
            await activate_subscription(payment.id, db_session)

    await db_session.refresh(payment)
    assert payment.status == PaymentStatus.paid

    from sqlalchemy import select
    result = await db_session.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    )
    sub = result.scalar_one()
    assert sub.status == SubscriptionStatus.active
    assert sub.devices_limit == 3


async def test_activate_creates_referral_transaction(db_session):
    referrer = User(telegram_id=200, username="ref")
    db_session.add(referrer)
    await db_session.commit()

    user = User(telegram_id=201, username="u2", referred_by=referrer.id)
    plan = Plan(name="Базовый", devices_limit=1, duration_days=30, price=Decimal("149.00"))
    db_session.add_all([user, plan])
    await db_session.commit()

    payment = Payment(
        user_id=user.id, plan_id=plan.id,
        provider=PaymentProvider.lava,
        external_id="lava_1",
        amount=Decimal("149.00"),
    )
    db_session.add(payment)
    await db_session.commit()

    with patch("bot.services.subscription.remnawave") as mock_remnawave:
        mock_remnawave.create_user = AsyncMock(return_value=("https://vpn.com/sub/xyz", "uuid-456"))
        with patch("bot.services.subscription.notify_user", new_callable=AsyncMock):
            await activate_subscription(payment.id, db_session)

    from sqlalchemy import select
    from bot.database.models import ReferralTransaction
    result = await db_session.execute(
        select(ReferralTransaction).where(ReferralTransaction.referrer_id == referrer.id)
    )
    ref_tx = result.scalar_one()
    assert ref_tx.amount == Decimal("44.70")  # 149 * 0.30
