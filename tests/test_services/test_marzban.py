import pytest
from unittest.mock import AsyncMock, MagicMock
from bot.services.marzban import MarzbanClient


@pytest.fixture
def client():
    return MarzbanClient(
        base_url="https://test.example.com",
        username="admin",
        password="password",
    )


async def test_create_user_returns_subscription_url(client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "username": "user_123",
        "subscription_url": "https://test.example.com/sub/abc123",
    }
    client._request = AsyncMock(return_value=mock_resp)

    url = await client.create_user("user_123", devices_limit=3, expire_days=30)
    assert url == "https://test.example.com/sub/abc123"
    client._request.assert_called_once()
    call_kwargs = client._request.call_args
    assert call_kwargs.args[0] == "POST"
    assert call_kwargs.args[1] == "/api/user"


async def test_delete_user(client):
    client._request = AsyncMock(return_value=MagicMock(status_code=200))
    await client.delete_user("user_123")
    client._request.assert_called_once_with("DELETE", "/api/user/user_123")
