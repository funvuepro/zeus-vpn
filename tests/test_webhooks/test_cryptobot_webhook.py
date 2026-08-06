import hashlib
import hmac
import json
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from bot.webhooks.app import create_app


def _make_cryptobot_signature(body: bytes, token: str) -> str:
    secret = hashlib.sha256(token.encode()).digest()
    return hmac.new(secret, body, hashlib.sha256).hexdigest()


@pytest.fixture
def app(db_session):
    return create_app(session_factory=lambda: db_session)


async def test_cryptobot_paid_webhook_activates_subscription(app, db_session):
    from bot.database.models import User, Plan, Payment, PaymentProvider

    user = User(telegram_id=777, username="payer")
    plan = Plan(name="Стандарт", devices_limit=3, duration_days=30, price=Decimal("249.00"))
    db_session.add_all([user, plan])
    await db_session.commit()

    payment = Payment(
        user_id=user.id,
        plan_id=plan.id,
        provider=PaymentProvider.cryptobot,
        external_id="invoice_42",
        amount=Decimal("249.00"),
    )
    db_session.add(payment)
    await db_session.commit()

    payload = {
        "update_type": "invoice_paid",
        "payload": {
            "payload": f"payment_id:{payment.id}",
            "status": "paid",
            "invoice_id": 42,
        },
    }

    body = json.dumps(payload).encode()
    signature = _make_cryptobot_signature(body, "test_cryptobot_token")

    with patch("bot.webhooks.cryptobot.activate_subscription", new_callable=AsyncMock) as mock_activate:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/webhook/cryptobot",
                content=body,
                headers={"content-type": "application/json", "crypto-pay-api-signature": signature},
            )
        assert resp.status_code == 200
        mock_activate.assert_called_once()
        assert mock_activate.call_args[0][0] == payment.id
