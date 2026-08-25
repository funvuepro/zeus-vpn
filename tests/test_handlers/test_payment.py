from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.database.models import Payment, PaymentProvider, PaymentStatus, User
from bot.handlers.payment import _validate_topup_amount, MIN_TOPUP_MESSAGE, set_devices


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


def _devices_callback(telegram_id: int, payload: str) -> MagicMock:
    callback = MagicMock()
    callback.data = payload
    callback.from_user.id = telegram_id
    callback.answer = AsyncMock()
    return callback


@pytest.mark.parametrize("payload", ["set_devices:-1", "set_devices:0", "set_devices:99", "set_devices:abc"])
async def test_set_devices_rejects_values_outside_allowed_options(db_session, payload):
    # devices_limit == -1 makes the daily charge 0.00 (free service forever),
    # devices_limit == 0 halves it — crafted callback_data must not be trusted.
    user = User(telegram_id=900, username="devs", devices_limit=3)
    db_session.add(user)
    await db_session.commit()

    await set_devices(_devices_callback(900, payload), db_session)

    await db_session.refresh(user)
    assert user.devices_limit == 3


async def test_set_devices_accepts_allowed_option(db_session):
    user = User(telegram_id=901, username="devs2", devices_limit=1, remnawave_uuid="42")
    db_session.add(user)
    await db_session.commit()

    with patch("bot.handlers.devices.smart_edit", new=AsyncMock()):
        await set_devices(_devices_callback(901, "set_devices:4"), db_session)

    await db_session.refresh(user)
    assert user.devices_limit == 4
