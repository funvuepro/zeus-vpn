from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from bot.database.models import Payment, PaymentProvider, PaymentStatus, User
from bot.services.referral import grant_referral_bonus, get_referral_registered_count, get_referral_paid_count

REFERRAL_BONUS_RUB = Decimal("100.00")


async def test_grant_referral_bonus_credits_referrer_once(db_session):
    referrer = User(telegram_id=600, username="referrer", balance=Decimal("0.00"))
    db_session.add(referrer)
    await db_session.commit()

    invited = User(telegram_id=601, username="invited", referred_by=referrer.id, balance=Decimal("0.00"))
    db_session.add(invited)
    await db_session.commit()

    payment = Payment(
        user_id=invited.id, provider=PaymentProvider.yookassa,
        amount=Decimal("150.00"), status=PaymentStatus.paid,
    )
    db_session.add(payment)
    await db_session.commit()

    await grant_referral_bonus(invited, db_session)

    await db_session.refresh(referrer)
    await db_session.refresh(invited)
    assert referrer.balance == REFERRAL_BONUS_RUB
    assert invited.referral_bonus_granted is True


async def test_grant_referral_bonus_is_not_repeated(db_session):
    referrer = User(telegram_id=602, username="referrer2", balance=Decimal("0.00"))
    db_session.add(referrer)
    await db_session.commit()

    invited = User(
        telegram_id=603, username="invited2", referred_by=referrer.id,
        balance=Decimal("0.00"), referral_bonus_granted=True,
    )
    db_session.add(invited)
    await db_session.commit()

    payment = Payment(
        user_id=invited.id, provider=PaymentProvider.yookassa,
        amount=Decimal("150.00"), status=PaymentStatus.paid,
    )
    db_session.add(payment)
    await db_session.commit()

    await grant_referral_bonus(invited, db_session)

    await db_session.refresh(referrer)
    assert referrer.balance == Decimal("0.00")  # already granted, no second credit


async def test_grant_referral_bonus_skips_non_first_payment(db_session):
    referrer = User(telegram_id=604, username="referrer3", balance=Decimal("0.00"))
    db_session.add(referrer)
    await db_session.commit()

    invited = User(telegram_id=605, username="invited3", referred_by=referrer.id, balance=Decimal("0.00"))
    db_session.add(invited)
    await db_session.commit()

    db_session.add_all([
        Payment(user_id=invited.id, provider=PaymentProvider.yookassa, amount=Decimal("100.00"), status=PaymentStatus.paid),
        Payment(user_id=invited.id, provider=PaymentProvider.yookassa, amount=Decimal("150.00"), status=PaymentStatus.paid),
    ])
    await db_session.commit()

    await grant_referral_bonus(invited, db_session)

    await db_session.refresh(referrer)
    assert referrer.balance == Decimal("0.00")  # this was the 2nd paid payment, not the 1st


async def test_grant_referral_bonus_reactivates_disabled_referrer(db_session):
    referrer = User(
        telegram_id=606, username="referrer4", balance=Decimal("0.00"),
        access_active=False, grace_started_at=datetime.now(timezone.utc),
        remnawave_uuid="uuid-ref",
    )
    db_session.add(referrer)
    await db_session.commit()

    invited = User(telegram_id=607, username="invited4", referred_by=referrer.id, balance=Decimal("0.00"))
    db_session.add(invited)
    await db_session.commit()

    payment = Payment(
        user_id=invited.id, provider=PaymentProvider.yookassa,
        amount=Decimal("150.00"), status=PaymentStatus.paid,
    )
    db_session.add(payment)
    await db_session.commit()

    with patch("bot.services.balance.remnawave") as mock_remnawave:
        mock_remnawave.enable_user = AsyncMock()
        await grant_referral_bonus(invited, db_session)
        mock_remnawave.enable_user.assert_called_once_with("uuid-ref")

    await db_session.refresh(referrer)
    assert referrer.balance == REFERRAL_BONUS_RUB
    assert referrer.access_active is True
    assert referrer.grace_started_at is None
