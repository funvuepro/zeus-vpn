from decimal import Decimal
from bot.database.models import Base, User, AppSettings, Payment, PaymentProvider, PaymentStatus


async def test_user_has_balance_fields(db_session):
    user = User(telegram_id=1, username="u")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    assert user.balance == Decimal("0.00")
    assert user.devices_limit == 1
    assert user.access_active is True
    assert user.grace_started_at is None
    assert user.referral_bonus_granted is False


async def test_app_settings_default_rate(db_session):
    row = AppSettings(id=1, daily_rate_per_device=Decimal("1.00"))
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    assert row.daily_rate_per_device == Decimal("1.00")


async def test_payment_provider_only_yookassa():
    assert [p.value for p in PaymentProvider] == ["yookassa"]


async def test_legacy_models_removed():
    import bot.database.models as m
    for name in ("Plan", "Subscription", "Withdrawal", "WithdrawalProvider", "ReferralTransaction"):
        assert not hasattr(m, name), f"{name} should have been removed"
