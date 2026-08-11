from decimal import Decimal
from unittest.mock import AsyncMock, patch

from bot.database.models import Payment, PaymentProvider, PaymentStatus, User
from bot.handlers.payment import _validate_topup_amount, MIN_TOPUP_MESSAGE


def test_validate_topup_amount_rejects_below_minimum():
    ok, error = _validate_topup_amount(50.0, min_amount=100.0)
    assert ok is False
    assert error == MIN_TOPUP_MESSAGE.format(min_amount=100.0)


def test_validate_topup_amount_accepts_minimum_and_above():
    ok, error = _validate_topup_amount(100.0, min_amount=100.0)
    assert ok is True
    assert error is None

    ok, error = _validate_topup_amount(250.0, min_amount=100.0)
    assert ok is True
