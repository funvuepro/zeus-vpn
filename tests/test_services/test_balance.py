from decimal import Decimal
from unittest.mock import AsyncMock, patch

from bot.database.models import AppSettings, Payment, PaymentProvider, PaymentStatus, User
from bot.services.balance import (
    calculate_daily_charge,
    get_daily_rate_per_device,
    set_daily_rate_per_device,
    credit_topup,
)


def test_calculate_daily_charge_scales_with_devices():
    rate = Decimal("1.00")
    assert calculate_daily_charge(rate, 1) == Decimal("1.00")
    assert calculate_daily_charge(rate, 2) == Decimal("1.50")
    assert calculate_daily_charge(rate, 3) == Decimal("2.00")


async def test_get_daily_rate_defaults_when_unset(db_session):
    rate = await get_daily_rate_per_device(db_session)
    assert rate == Decimal("1.00")


async def test_set_then_get_daily_rate(db_session):
    await set_daily_rate_per_device(db_session, Decimal("2.50"))
    rate = await get_daily_rate_per_device(db_session)
    assert rate == Decimal("2.50")


async def test_credit_topup_adds_balance_and_marks_paid(db_session):
    user = User(telegram_id=500, username="topupper", balance=Decimal("0.00"))
    db_session.add(user)
    await db_session.commit()

    payment = Payment(user_id=user.id, provider=PaymentProvider.yookassa, amount=Decimal("150.00"))
    db_session.add(payment)
    await db_session.commit()

    await credit_topup(payment.id, Decimal("150.00"), "yk_ext_1", db_session)

    await db_session.refresh(user)
    await db_session.refresh(payment)
    assert user.balance == Decimal("150.00")
    assert payment.status == PaymentStatus.paid
    assert payment.external_id == "yk_ext_1"


async def test_credit_topup_is_idempotent(db_session):
    user = User(telegram_id=501, username="twice", balance=Decimal("0.00"))
    db_session.add(user)
    await db_session.commit()

    payment = Payment(user_id=user.id, provider=PaymentProvider.yookassa, amount=Decimal("150.00"))
    db_session.add(payment)
    await db_session.commit()

    await credit_topup(payment.id, Decimal("150.00"), "yk_ext_1", db_session)
    await credit_topup(payment.id, Decimal("150.00"), "yk_ext_1", db_session)

    await db_session.refresh(user)
    assert user.balance == Decimal("150.00")  # not credited twice


async def test_credit_topup_reactivates_disabled_access(db_session):
    from datetime import datetime, timezone
    user = User(
        telegram_id=502, username="reactivate", balance=Decimal("0.00"),
        access_active=False, grace_started_at=datetime.now(timezone.utc),
        remnawave_uuid="uuid-1",
    )
    db_session.add(user)
    await db_session.commit()

    payment = Payment(user_id=user.id, provider=PaymentProvider.yookassa, amount=Decimal("100.00"))
    db_session.add(payment)
    await db_session.commit()

    with patch("bot.services.balance.remnawave") as mock_remnawave:
        mock_remnawave.enable_user = AsyncMock()
        await credit_topup(payment.id, Decimal("100.00"), "yk_ext_2", db_session)
        mock_remnawave.enable_user.assert_called_once_with("uuid-1")

    await db_session.refresh(user)
    assert user.access_active is True
    assert user.grace_started_at is None


async def test_credit_topup_grants_referral_bonus_on_first_payment(db_session):
    from bot.services.balance import credit_topup

    referrer = User(telegram_id=510, username="ref", balance=Decimal("0.00"))
    db_session.add(referrer)
    await db_session.commit()

    invited = User(telegram_id=511, username="invited", referred_by=referrer.id, balance=Decimal("0.00"))
    db_session.add(invited)
    await db_session.commit()

    payment = Payment(user_id=invited.id, provider=PaymentProvider.yookassa, amount=Decimal("150.00"))
    db_session.add(payment)
    await db_session.commit()

    await credit_topup(payment.id, Decimal("150.00"), "yk_ext_ref", db_session)

    await db_session.refresh(referrer)
    assert referrer.balance == Decimal("100.00")
