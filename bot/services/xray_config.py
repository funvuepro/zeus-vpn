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
            "authority": "",
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


def build_xray_config(user_uuid: str, servers: list[VpnServer], title: str = "DS-VPN") -> dict:
    primary = [s for s in servers if not s.is_backup]
    backup = [s for s in servers if s.is_backup]

    outbounds = []
    primary_tags = []
    backup_tags = []

    for i, server in enumerate(primary):
        tag = "proxy" if i == 0 else f"proxy-{i}"
        outbounds.append(_make_outbound(server, user_uuid, tag))
        primary_tags.append(tag)

    for i, server in enumerate(backup):
        tag = f"backup-{i}"
        outbounds.append(_make_outbound(server, user_uuid, tag))
        backup_tags.append(tag)

    outbounds += [
        {"protocol": "freedom", "tag": "direct"},
        {"protocol": "blackhole", "tag": "block"},
    ]

    balancers = []
    routing_rules = [
        {"outboundTag": "direct", "protocol": ["bittorrent"], "type": "field"},
        {"domain": _RU_BYPASS_DOMAINS, "outboundTag": "direct", "type": "field"},
    ]

    if primary_tags:
        balancers.append({
            "tag": "main_balancer",
            "selector": primary_tags,
            "strategy": {"type": "leastPing"},
            **({"fallbackTag": "backup_balancer"} if backup_tags else {}),
        })
        routing_rules.append({"balancerTag": "main_balancer", "type": "field", "network": "tcp,udp"})

    if backup_tags:
        balancers.append({
            "tag": "backup_balancer",
            "selector": backup_tags,
            "strategy": {"type": "leastPing"},
        })

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

    if len(primary_tags) > 1 or backup_tags:
        config["burstObservatory"] = {
            "pingConfig": {
                "connectivity": "http://connectivitycheck.platform.hicloud.com/generate_204",
                "destination": "https://www.google.com/generate_204",
                "interval": "30s",
                "sampling": 3,
                "timeout": "5s",
            },
            "subjectSelector": ["proxy"],
        }

    return config
