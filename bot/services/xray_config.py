from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bot.database.models import VpnServer

# Russian domains that must bypass VPN (go direct)
_RU_BYPASS_DOMAINS = [
    "domain:gosuslugi.ru", "domain:esia.gosuslugi.ru", "domain:gov.ru",
    "domain:nalog.ru", "domain:mos.ru",
    "domain:vk.com", "domain:vk.ru", "domain:vkontakte.com", "domain:userapi.com",
    "domain:vkcdn.net", "domain:vk-cdn.net", "domain:vkuser.net",
    "domain:vkvideo.ru", "domain:vkplay.ru", "domain:vkpay.io",
    "domain:ok.ru", "domain:odnoklassniki.ru", "domain:okcdn.ru",
    "domain:mail.ru", "domain:cloud.mail.ru", "domain:imgsmail.ru",
    "domain:max.ru", "domain:api.max.ru", "domain:cdn.max.ru",
    "domain:yandex.ru", "domain:ya.ru", "domain:yandex.net",
    "domain:dzen.ru", "domain:kinopoisk.ru",
    "domain:ozon.ru", "domain:ozoncdn.com",
    "domain:avito.ru",
    "domain:sber.ru", "domain:sberbank.ru",
    "domain:tinkoff.ru", "domain:alfabank.ru",
    "domain:mts.ru", "domain:beeline.ru", "domain:megafon.ru", "domain:tele2.ru",
    "domain:rutube.ru",
]

_DNS_CONFIG = {
    "disableCache": False,
    "disableFallback": False,
    "disableFallbackIfMatch": False,
    "hosts": {
        "domain:googleapis.cn": "googleapis.com",
        "one.one.one.one": ["1.1.1.1", "1.0.0.1"],
    },
    "queryStrategy": "UseIPv4",
    "servers": [
        {"address": "https://9.9.9.9/dns-query", "tag": "quad9"},
        {"address": "https://1.1.1.1/dns-query", "tag": "cloudflare"},
    ],
}

_INBOUNDS = [
    {
        "listen": "127.0.0.1", "port": 10808, "protocol": "socks",
        "settings": {"auth": "noauth", "udp": True},
        "sniffing": {"destOverride": ["http", "tls", "quic"], "enabled": True, "routeOnly": False},
        "tag": "socks",
    },
    {
        "listen": "127.0.0.1", "port": 10809, "protocol": "http",
        "settings": {"allowTransparent": False},
        "sniffing": {"destOverride": ["http", "tls", "quic"], "enabled": True, "routeOnly": False},
        "tag": "http",
    },
]


def _make_outbound(server: VpnServer, user_uuid: str, tag: str) -> dict:
    if server.protocol == "hysteria2":
        # Not a real Xray-core transport -- this dialect ("protocol": "hysteria",
        # version 2) is only understood by Happ's bundled client, which parses it
        # itself and runs a separate Hysteria2 process for these legs. Plain
        # xray-core rejects "hysteria2"/"hysteria" as an unknown transport, so this
        # outbound can only be exercised end-to-end through Happ, not `xray run`.
        return {
            "protocol": "hysteria",
            "settings": {
                "address": server.ip,
                "port": server.port,
                "version": 2,
            },
            "streamSettings": {
                "network": "hysteria",
                "security": "tls",
                "hysteriaSettings": {
                    "auth": server.auth_password,
                    "version": 2,
                },
                "tlsSettings": {
                    "alpn": ["h3"],
                    "enableSessionResumption": False,
                    "fingerprint": server.fingerprint,
                    "serverName": server.server_name,
                },
            },
            "tag": tag,
        }

    stream: dict = {"security": "reality"}

    reality_settings = {
        "fingerprint": server.fingerprint,
        "publicKey": server.public_key,
        "serverName": server.server_name,
        "shortId": server.short_id,
    }

    if server.transport == "grpc":
        stream["network"] = "grpc"
        stream["grpcSettings"] = {
            # Matches serverName (the Reality decoy domain) so the :authority
            # header doesn't stick out against the masqueraded TLS handshake.
            "authority": server.server_name or "",
            "mode": False,
            "serviceName": server.service_name or "grpc",
        }
        stream["realitySettings"] = reality_settings
        flow = ""
    else:
        stream["network"] = "tcp"
        stream["tcpSettings"] = {}
        stream["realitySettings"] = reality_settings
        flow = "xtls-rprx-vision"

    return {
        "protocol": "vless",
        "settings": {
            "vnext": [{
                "address": server.ip,
                "port": server.port,
                "users": [{"encryption": "none", "flow": flow, "id": user_uuid}],
            }]
        },
        "streamSettings": stream,
        "tag": tag,
    }


_TIERS = ("msk", "lte", "llp")

# Cascade order: msk falls back to lte, lte falls back to llp, llp is last resort.
# A tier's fallback is reached via a "loopback" outbound that re-injects the
# connection into routing tagged as coming from a virtual inbound (LTE-REROUTE /
# LLP-REROUTE); a routing rule then hands that re-injected traffic to the next
# tier's balancer. This indirection is what lets one balancer's fallbackTag
# effectively point at *another balancer* instead of only a plain outbound.
_LOOPBACK_TAG = {"lte": "LOOP-LTE", "llp": "LOOP-LLP"}
_REROUTE_INBOUND_TAG = {"lte": "LTE-REROUTE", "llp": "LLP-REROUTE"}
_BALANCER_TAG = {tier: f"{tier}_balancer" for tier in _TIERS}


def build_xray_config(user_uuid: str, servers: list[VpnServer], title: str = "Zeus VPN") -> dict:
    tier_tags: dict[str, list[str]] = {tier: [] for tier in _TIERS}
    outbounds = []

    for tier in _TIERS:
        tier_servers = [s for s in servers if s.tier == tier]
        for i, server in enumerate(tier_servers):
            tag = f"{tier.upper()}-{i}"
            outbounds.append(_make_outbound(server, user_uuid, tag))
            tier_tags[tier].append(tag)

    outbounds += [
        {"protocol": "freedom", "tag": "direct"},
        {"protocol": "blackhole", "tag": "block"},
    ]
    for tier in ("lte", "llp"):
        if tier_tags[tier]:
            outbounds.append({
                "protocol": "loopback",
                "settings": {"inboundTag": _REROUTE_INBOUND_TAG[tier]},
                "tag": _LOOPBACK_TAG[tier],
            })

    # The next present tier after `tier`, used both as a balancer's fallbackTag
    # target and to decide which tier the catch-all routing rule should enter at.
    def _next_tier(tier: str) -> str | None:
        remaining = _TIERS[_TIERS.index(tier) + 1:]
        return next((t for t in remaining if tier_tags[t]), None)

    balancers = []
    routing_rules = [
        {"outboundTag": "direct", "protocol": ["bittorrent"], "type": "field"},
        {"domain": _RU_BYPASS_DOMAINS, "outboundTag": "direct", "type": "field"},
    ]

    # Loopback re-entry rules must be evaluated before the catch-all entry rule
    # below, since they match traffic that has already been routed once.
    for tier in ("lte", "llp"):
        if tier_tags[tier]:
            routing_rules.append({
                "type": "field",
                "inboundTag": [_REROUTE_INBOUND_TAG[tier]],
                "balancerTag": _BALANCER_TAG[tier],
            })

    for tier in _TIERS:
        if not tier_tags[tier]:
            continue
        fallback = _next_tier(tier)
        balancers.append({
            "tag": _BALANCER_TAG[tier],
            "selector": tier_tags[tier],
            "strategy": {"type": "leastPing"},
            **({"fallbackTag": _LOOPBACK_TAG[fallback]} if fallback else {}),
        })

    entry_tier = next((t for t in _TIERS if tier_tags[t]), None)
    if entry_tier:
        routing_rules.append({"balancerTag": _BALANCER_TAG[entry_tier], "type": "field", "network": "tcp,udp"})

    config: dict = {
        "remarks": f"🇷🇺 {title} — Автовыбор",
        "meta": {"serverDescription": f"✅ {title} — подождите 30 сек для выбора сервера"},
        "log": {"loglevel": "warning"},
        "dns": _DNS_CONFIG,
        "inbounds": _INBOUNDS,
        "outbounds": outbounds,
        "routing": {
            "balancers": balancers,
            "domainMatcher": "hybrid",
            "domainStrategy": "IPIfNonMatch",
            "rules": routing_rules,
        },
        "policy": {
            "system": {
                "statsInboundDownlink": True,
                "statsInboundUplink": True,
                "statsOutboundDownlink": True,
                "statsOutboundUplink": True,
            }
        },
    }

    all_proxy_tags = [tag for tier in _TIERS for tag in tier_tags[tier]]
    if len(all_proxy_tags) > 1:
        config["burstObservatory"] = {
            "pingConfig": {
                "connectivity": "http://connectivitycheck.platform.hicloud.com/generate_204",
                "destination": "https://www.google.com/generate_204",
                "interval": "30s",
                "sampling": 3,
                "timeout": "5s",
            },
            "subjectSelector": [tier.upper() for tier in _TIERS if tier_tags[tier]],
        }

    return config
