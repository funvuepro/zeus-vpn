from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

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
