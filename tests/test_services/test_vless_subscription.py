import base64
from unittest.mock import AsyncMock, Mock

import pytest
from starlette.requests import Request

from bot.database.models import VpnServer
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


async def test_grpc_links_are_dropped(monkeypatch):
    # Confirmed live on 2026-09-20 via packet capture on the relay node: every
    # grpc connection attempt from the real Happ client falls through to
    # Reality's decoy-proxy fallback (byte-for-byte mirrored to the decoy site
    # instead of tunneling), while the identical link works fine from plain
    # xray-core -- a client-side uTLS mismatch, not a server misconfiguration.
    # tcp must survive; grpc must not, regardless of node health.
    payload = {
        'isFound': True,
        'links': [
            'vless://a@1.1.1.1:443?type=tcp&flow=xtls-rprx-vision#zeus-lte-aeza-tcp',
            'vless://a@1.1.1.1:8443?type=grpc&serviceName=grpc#zeus-lte-aeza-grpc',
        ],
    }
    response = Mock(status_code=200)
    response.json.return_value = payload
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.get.return_value = response
    monkeypatch.setattr(subscription.httpx, 'AsyncClient', lambda: client)
    monkeypatch.setattr(subscription, '_remnawave_base', lambda: 'https://example.test')

    result = await subscription.xray_config('test', Request({'type': 'http'}))

    assert result.status_code == 200
    kept = base64.b64decode(result.body, validate=True).decode().splitlines()
    assert kept == ['vless://a@1.1.1.1:443?type=tcp&flow=xtls-rprx-vision#zeus-lte-aeza-tcp']


@pytest.mark.skip(reason="hysteria2 append disabled live 2026-09-20 -- unconfirmed whether Happ's link-list parser tolerates an unknown scheme or aborts the whole parse on it")
async def test_hysteria2_servers_are_appended_to_the_subscription(monkeypatch, db_session):
    # Hysteria2/QUIC nodes are a separate hysteria container, not a
    # Remnawave-managed Xray inbound, so Remnawave's own link list never
    # includes them -- they have to be appended from our own DB. This matters
    # more now that Russian DPI (TSPU) fingerprints VLESS+TCP+Reality traffic
    # behaviorally: QUIC doesn't match that pattern at all.
    db_session.add(VpnServer(
        name="zeus-llp-aeza", ip="109.120.132.0", port=8444, protocol="hysteria2",
        transport="tcp", fingerprint="edge", server_name="yastatic.net",
        cert_name="llp.krzmihome.ru", auth_password="secretpass", is_active=True,
    ))
    await db_session.commit()

    payload = {
        'isFound': True,
        'links': ['vless://a@1.1.1.1:443?type=tcp&flow=xtls-rprx-vision#zeus-lte-aeza-tcp'],
    }
    response = Mock(status_code=200)
    response.json.return_value = payload
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.get.return_value = response
    monkeypatch.setattr(subscription.httpx, 'AsyncClient', lambda: client)
    monkeypatch.setattr(subscription, '_remnawave_base', lambda: 'https://example.test')

    result = await subscription.xray_config('test', Request({'type': 'http'}))

    assert result.status_code == 200
    kept = base64.b64decode(result.body, validate=True).decode().splitlines()
    assert 'vless://a@1.1.1.1:443?type=tcp&flow=xtls-rprx-vision#zeus-lte-aeza-tcp' in kept
    hy2 = next(l for l in kept if l.startswith('hysteria2://'))
    assert hy2 == 'hysteria2://secretpass@109.120.132.0:8444/?sni=llp.krzmihome.ru&insecure=0#zeus-llp-aeza'


@pytest.mark.skip(reason="hysteria2 append disabled live 2026-09-20 -- unconfirmed whether Happ's link-list parser tolerates an unknown scheme or aborts the whole parse on it")
async def test_hysteria2_link_dropped_when_its_ip_shares_a_dead_node(monkeypatch, db_session):
    # Most hysteria2 boxes are the same physical Selectel VM as an MSK/LTE
    # node, just a different port -- Remnawave's node-connectivity check has
    # no idea hysteria2 is even running there, so it has to be matched by IP.
    db_session.add(VpnServer(
        name="zeus-llp-1", ip="89.223.30.168", port=8444, protocol="hysteria2",
        transport="tcp", fingerprint="edge", server_name="yastatic.net",
        cert_name="llp.krzmihome.ru", auth_password="deadpass", is_active=True,
    ))
    db_session.add(VpnServer(
        name="zeus-llp-aeza", ip="109.120.132.0", port=8444, protocol="hysteria2",
        transport="tcp", fingerprint="edge", server_name="yastatic.net",
        cert_name="llp.krzmihome.ru", auth_password="alivepass", is_active=True,
    ))
    await db_session.commit()

    sub_payload = {'isFound': True, 'links': ['vless://a@1.1.1.1:443?x=1#zeus-lte-aeza-tcp']}
    nodes_payload = {'response': [{'name': 'zeus-lte-1', 'isConnected': False, 'address': '89.223.30.168'}]}
    sub_response = Mock(status_code=200)
    sub_response.json.return_value = sub_payload
    nodes_response = Mock(status_code=200)
    nodes_response.json.return_value = nodes_payload
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.get.side_effect = [sub_response, nodes_response]
    monkeypatch.setattr(subscription.httpx, 'AsyncClient', lambda: client)
    monkeypatch.setattr(subscription, '_remnawave_base', lambda: 'https://example.test')

    result = await subscription.xray_config('test', Request({'type': 'http'}))

    kept = base64.b64decode(result.body, validate=True).decode().splitlines()
    hy2_links = [l for l in kept if l.startswith('hysteria2://')]
    assert hy2_links == ['hysteria2://alivepass@109.120.132.0:8444/?sni=llp.krzmihome.ru&insecure=0#zeus-llp-aeza']


async def test_llp_subscription_serves_only_hysteria2_links(monkeypatch, db_session):
    # Confirmed live 2026-09-20: QUIC/hysteria2 is the one transport that
    # actually gets through TSPU's behavioral fingerprinting of
    # VLESS+TCP+Reality (raw and gRPC alike). Mixing a hysteria2:// line into
    # the vless link list broke the whole list in Happ, so it's served as
    # its own separate subscription instead.
    db_session.add(VpnServer(
        name="zeus-llp-aeza", ip="109.120.132.0", port=8444, protocol="hysteria2",
        transport="tcp", fingerprint="edge", server_name="yastatic.net",
        cert_name="llp.krzmihome.ru", auth_password="secretpass", is_active=True,
    ))
    await db_session.commit()

    payload = {'isFound': True, 'links': ['vless://a@1.1.1.1:443?x=1#zeus-lte-aeza-tcp']}
    response = Mock(status_code=200)
    response.json.return_value = payload
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.get.return_value = response
    monkeypatch.setattr(subscription.httpx, 'AsyncClient', lambda: client)
    monkeypatch.setattr(subscription, '_remnawave_base', lambda: 'https://example.test')

    result = await subscription.xray_llp_config('test', Request({'type': 'http'}))

    assert result.status_code == 200
    kept = base64.b64decode(result.body, validate=True).decode().splitlines()
    assert kept == ['hysteria2://secretpass@109.120.132.0:8444/?sni=llp.krzmihome.ru&insecure=0#zeus-llp-aeza']


async def test_llp_subscription_503s_when_no_hysteria2_servers(monkeypatch):
    payload = {'isFound': True, 'links': []}
    response = Mock(status_code=200)
    response.json.return_value = payload
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.get.return_value = response
    monkeypatch.setattr(subscription.httpx, 'AsyncClient', lambda: client)
    monkeypatch.setattr(subscription, '_remnawave_base', lambda: 'https://example.test')

    result = await subscription.xray_llp_config('test', Request({'type': 'http'}))

    assert result.status_code == 503


async def test_links_to_unreachable_nodes_are_dropped(monkeypatch):
    # Not hypothetical: an entire provider account can go dark at once (this
    # is exactly what happened to Selectel on 2026-09-20 -- 11 of 12 nodes
    # EHOSTUNREACH simultaneously). A client that pins to one of those dead
    # links "connects but nothing loads" until the 12h profile-update-interval
    # rolls around, so a still-down node's links must not be served at all.
    sub_payload = {
        'isFound': True,
        'links': [
            'vless://a@1.1.1.1:443?x=1#zeus-msk-1',
            'vless://b@2.2.2.2:443?x=1#zeus-lte-1-tcp',
            'vless://c@2.2.2.2:8443?x=1#zeus-lte-1-grpc',
            'vless://d@3.3.3.3:443?x=1#zeus-lte-10-tcp',
            'vless://e@4.4.4.4:443?x=1#zeus-lte-aeza-tcp',
        ],
    }
    nodes_payload = {
        'response': [
            {'name': 'zeus-msk-1', 'isConnected': False},
            {'name': 'zeus-lte-1', 'isConnected': False},
            {'name': 'zeus-lte-10', 'isConnected': True},
            {'name': 'zeus-lte-aeza', 'isConnected': True},
        ]
    }
    sub_response = Mock(status_code=200)
    sub_response.json.return_value = sub_payload
    nodes_response = Mock(status_code=200)
    nodes_response.json.return_value = nodes_payload
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.get.side_effect = [sub_response, nodes_response]
    monkeypatch.setattr(subscription.httpx, 'AsyncClient', lambda: client)
    monkeypatch.setattr(subscription, '_remnawave_base', lambda: 'https://example.test')

    result = await subscription.xray_config('test', Request({'type': 'http'}))

    assert result.status_code == 200
    kept = base64.b64decode(result.body, validate=True).decode().splitlines()
    # zeus-msk-1 and zeus-lte-1(-tcp/-grpc) are down and must be dropped;
    # zeus-lte-10 must survive despite "zeus-lte-1" being a prefix of its
    # name, and zeus-lte-aeza (up) must survive too.
    assert kept == [
        'vless://d@3.3.3.3:443?x=1#zeus-lte-10-tcp',
        'vless://e@4.4.4.4:443?x=1#zeus-lte-aeza-tcp',
    ]
