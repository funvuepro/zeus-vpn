from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from bot.webhooks.app import create_app


class _SessionContextManager:
    """Context manager wrapper that doesn't close the session."""
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *args):
        pass


@pytest.fixture
def app(db_session):
    return create_app(session_factory=lambda: _SessionContextManager(db_session))


async def test_payment_succeeded_credits_balance(app, db_session):
    from bot.database.models import User, Payment, PaymentProvider

    user = User(telegram_id=900, username="payer")
    db_session.add(user)
    await db_session.commit()

    payment = Payment(user_id=user.id, provider=PaymentProvider.yookassa, amount=Decimal("150.00"))
    db_session.add(payment)
    await db_session.commit()

    webhook_body = {
        "event": "payment.succeeded",
        "object": {"id": "yk_ext_99"},
    }
    status_response = {
        "id": "yk_ext_99",
        "status": "succeeded",
        "amount": {"value": "150.00", "currency": "RUB"},
        "metadata": {"payment_id": str(payment.id)},
    }

    with patch("bot.webhooks.yookassa.get_payment_status", new_callable=AsyncMock) as mock_status:
        mock_status.return_value = status_response
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/webhook/yookassa", json=webhook_body)

    assert resp.status_code == 200
    await db_session.refresh(user)
    assert user.balance == Decimal("150.00")


async def test_non_succeeded_event_is_ignored(app, db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/webhook/yookassa", json={"event": "payment.canceled", "object": {"id": "x"}})
    assert resp.status_code == 200
