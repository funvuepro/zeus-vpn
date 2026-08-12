from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from bot.database.models import PromoCode, User
from bot.handlers.promo import redeem_promo_code


async def test_redeem_promo_code_credits_balance(db_session):
    user = User(telegram_id=800, username="promouser", balance=Decimal("0.00"))
    promo = PromoCode(code="ZEUS50", amount=50)
    db_session.add_all([user, promo])
    await db_session.commit()

    message = MagicMock()
    message.from_user.id = 800
    message.text = "ZEUS50"
    message.answer = AsyncMock()

    await redeem_promo_code(message, db_session)

    await db_session.refresh(user)
    assert user.balance == Decimal("50.00")
    message.answer.assert_called_once()


async def test_redeem_promo_code_rejects_reuse(db_session):
    user = User(telegram_id=801, username="promouser2", balance=Decimal("0.00"))
    promo = PromoCode(code="ONESHOT", amount=30)
    db_session.add_all([user, promo])
    await db_session.commit()

    message = MagicMock()
    message.from_user.id = 801
    message.text = "ONESHOT"
    message.answer = AsyncMock()

    await redeem_promo_code(message, db_session)
    await db_session.refresh(user)
    assert user.balance == Decimal("30.00")

    message2 = MagicMock()
    message2.from_user.id = 801
    message2.text = "ONESHOT"
    message2.answer = AsyncMock()
    await redeem_promo_code(message2, db_session)

    await db_session.refresh(user)
    assert user.balance == Decimal("30.00")  # unchanged — already used


async def test_redeem_promo_code_reactivates_disabled_access(db_session):
    # run_daily_billing only touches users with access_active == True, so a promo
    # top-up must lift grace/disabled state exactly like a paid top-up does.
    user = User(
        telegram_id=802,
        username="disabled",
        balance=Decimal("0.00"),
        access_active=False,
        grace_started_at=datetime.now(timezone.utc),
        remnawave_uuid="uuid-promo",
    )
    promo = PromoCode(code="REVIVE", amount=40)
    db_session.add_all([user, promo])
    await db_session.commit()

    message = MagicMock()
    message.from_user.id = 802
    message.text = "REVIVE"
    message.answer = AsyncMock()

    with patch("bot.services.balance.remnawave") as mock_remnawave:
        mock_remnawave.enable_user = AsyncMock()
        await redeem_promo_code(message, db_session)
        mock_remnawave.enable_user.assert_called_once_with("uuid-promo")

    await db_session.refresh(user)
    assert user.balance == Decimal("40.00")
    assert user.access_active is True
    assert user.grace_started_at is None


async def test_redeem_promo_code_ignores_unregistered_user(db_session):
    message = MagicMock()
    message.from_user.id = 999999
    message.text = "ANY"
    message.answer = AsyncMock()

    await redeem_promo_code(message, db_session)

    message.answer.assert_not_called()
