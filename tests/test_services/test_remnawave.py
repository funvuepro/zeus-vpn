import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock
from bot.services.remnawave import RemnaWaveClient


@pytest.fixture
def client():
    return RemnaWaveClient(
        base_url="https://test.example.com",
        api_token="test-token-abc",
    )


async def test_create_user_returns_url_and_uuid(client):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "response": {
            "uuid": "aaaa-bbbb-cccc",
            "subscriptionUrl": "https://test.example.com/sub/xyz",
        }
    }
    client._request = AsyncMock(return_value=mock_resp)

    url, uuid = await client.create_user("user_123", expire_days=30)
    assert url == "https://test.example.com/sub/xyz"
    assert uuid == "aaaa-bbbb-cccc"
    call = client._request.call_args
    assert call.args[0] == "POST"
    assert call.args[1] == "/users"
    payload = call.kwargs["json"]
    assert payload["username"] == "user_123"
    assert payload["status"] == "ACTIVE"
    assert "expireAt" in payload


async def test_extend_user_passes_absolute_datetime(client):
    client._request = AsyncMock(return_value=MagicMock())
    expire_at = datetime(2026, 6, 30, 12, 0, 0, tzinfo=timezone.utc)

    await client.extend_user("user_123", expire_at)
    call = client._request.call_args
    assert call.args[0] == "PATCH"
    assert call.args[1] == "/users"
    payload = call.kwargs["json"]
    assert payload["username"] == "user_123"
    assert payload["expireAt"] == "2026-06-30T12:00:00Z"
    assert payload["status"] == "ACTIVE"


async def test_disable_user_uses_uuid(client):
    client._request = AsyncMock(return_value=MagicMock())
    await client.disable_user("aaaa-bbbb-cccc")
    client._request.assert_called_once_with("POST", "/users/aaaa-bbbb-cccc/actions/disable")


async def test_enable_user_uses_uuid(client):
    client._request = AsyncMock(return_value=MagicMock())
    await client.enable_user("aaaa-bbbb-cccc")
    client._request.assert_called_once_with("POST", "/users/aaaa-bbbb-cccc/actions/enable")


async def test_delete_user_uses_uuid(client):
    client._request = AsyncMock(return_value=MagicMock())
    await client.delete_user("aaaa-bbbb-cccc")
    client._request.assert_called_once_with("DELETE", "/users/aaaa-bbbb-cccc")


async def test_get_subscription_url(client):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "response": {"subscriptionUrl": "https://test.example.com/sub/xyz"}
    }
    client._request = AsyncMock(return_value=mock_resp)

    url = await client.get_subscription_url("user_123")
    assert url == "https://test.example.com/sub/xyz"
    client._request.assert_called_once_with("GET", "/users/by-username/user_123")


async def test_bearer_token_in_header(client):
    http = client._get_http()
    assert http.headers["Authorization"] == "Bearer test-token-abc"
