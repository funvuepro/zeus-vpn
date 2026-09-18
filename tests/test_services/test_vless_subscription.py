import base64
from unittest.mock import AsyncMock, Mock

import pytest
from starlette.requests import Request

from bot.webhooks import subscription


@pytest.mark.parametrize(
    'payload,status,expected',
    [
        ({'isFound': True, 'links': ['vless://one', 'hysteria2://two', 'vless://three']}, 200, ['vless://one', 'vless://three']),
        ({'isFound': True, 'links': []}, 503, None),
        ({'isFound': False}, 404, None),
    ],
)
async def test_link_subscription(monkeypatch, payload, status, expected):
    response = Mock(status_code=200)
    response.json.return_value = payload
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.get.return_value = response
    monkeypatch.setattr(subscription.httpx, 'AsyncClient', lambda: client)
    monkeypatch.setattr(subscription, '_remnawave_base', lambda: 'https://example.test')
    result = await subscription.xray_config('test', Request({'type': 'http'}))
    assert result.status_code == status
    if expected is not None:
        assert result.media_type == 'text/plain'
        assert base64.b64decode(result.body, validate=True).decode().splitlines() == expected
