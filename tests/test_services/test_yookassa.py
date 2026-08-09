from unittest.mock import AsyncMock, MagicMock

import bot.services.yookassa as yk


def _mock_async_client(monkeypatch, response_json, method="post"):
    mock_resp = MagicMock()
    mock_resp.json.return_value = response_json
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    setattr(mock_client, method, AsyncMock(return_value=mock_resp))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(yk.httpx, "AsyncClient", lambda **kw: mock_client)
    return mock_client


async def test_create_payment_returns_confirmation_url(monkeypatch):
    mock_client = _mock_async_client(monkeypatch, {
        "id": "yk_1", "confirmation": {"confirmation_url": "https://yookassa.ru/pay/abc"},
    }, method="post")

    url = await yk.create_payment(150.0, 42, "Пополнение баланса Zeus VPN")

    assert url == "https://yookassa.ru/pay/abc"
    call = mock_client.post.call_args
    assert call.args[0] == f"{yk.YOOKASSA_API}/payments"
    body = call.kwargs["json"]
    assert body["amount"] == {"value": "150.00", "currency": "RUB"}
    assert body["metadata"] == {"payment_id": "42"}
    assert "Idempotence-Key" in call.kwargs["headers"]


async def test_get_payment_status_returns_full_payload(monkeypatch):
    payload = {"id": "yk_1", "status": "succeeded", "amount": {"value": "150.00", "currency": "RUB"}}
    mock_client = _mock_async_client(monkeypatch, payload, method="get")

    result = await yk.get_payment_status("yk_1")

    assert result == payload
    call = mock_client.get.call_args
    assert call.args[0] == f"{yk.YOOKASSA_API}/payments/yk_1"
