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

# Explicit domains + Telegram's own published CIDR ranges (core.telegram.org/
# resources/cidr.txt), not "geosite:telegram"/"geoip:telegram" -- those rely on
# a geo database being bundled in whatever Xray build the client ships, and an
# unresolvable category can fail the *entire* routing config to load, not just
# the Telegram rule. An explicit list always parses.
_TELEGRAM_DOMAINS = [
    "domain:telegram.org", "domain:telegram.me", "domain:t.me",
    "domain:telesco.pe", "domain:tdesktop.com", "domain:telegra.ph",
    "domain:telegramdesktop.com", "domain:graph.org",
]
_TELEGRAM_CIDRS = [
    "91.108.4.0/22", "91.108.8.0/22", "91.108.12.0/22", "91.108.16.0/22",
    "91.108.20.0/22", "91.108.56.0/22", "91.105.192.0/23",
    "149.154.160.0/20", "149.154.164.0/22", "149.154.168.0/22", "149.154.172.0/22",
    "95.161.64.0/20",
    "185.76.151.0/24",
    # IPv6 matters as much as v4 here: Telegram is fully v6-enabled and mobile
    # carriers hand out v6 by default, so the app reaches its DCs over v6 and
    # a v4-only match list quietly lets that traffic past the relay and into a
    # tier that can't reach Telegram at all.
    "2001:b28:f23c::/48", "2001:b28:f23d::/48", "2001:b28:f23f::/48",
    "2001:67c:4e8::/48", "2a0a:f280::/32",
]

# Meta (Instagram/Facebook/WhatsApp) is on Roskomnadzor's blocklist and
# Selectel enforces it at their network edge, same as Telegram -- confirmed by
# a plain curl straight from a Selectel node timing out on instagram.com,
# facebook.com and web.whatsapp.com alike with no VPN involved at all. Same
# relay, same reasoning: explicit list, not geosite/geoip.
_META_DOMAINS = [
    "domain:instagram.com", "domain:cdninstagram.com",
    "domain:facebook.com", "domain:fb.com", "domain:facebook.net", "domain:fbcdn.net",
    "domain:whatsapp.com", "domain:whatsapp.net",
    "domain:messenger.com",
]
_META_CIDRS = [
    "157.240.0.0/16", "31.13.24.0/21", "31.13.64.0/18",
    "69.171.224.0/19", "69.63.176.0/20", "66.220.144.0/20",
    "179.60.192.0/22", "185.60.216.0/22", "185.89.216.0/22",
    "102.132.96.0/20", "103.4.96.0/22", "129.134.0.0/16",
    "173.252.64.0/18", "204.15.20.0/22", "45.64.40.0/22", "74.119.76.0/22",
    "2a03:2880::/32", "2a03:2887::/32", "2401:db00::/32",
    "2620:0:1c00::/40", "2803:6080::/32",
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
                # QUIC tuning the competitor's working config carries. Path MTU
                # discovery off matters most: QUIC sets DF on every datagram, and
                # a black-holed "fragmentation needed" ICMP anywhere on a mobile
                # path stalls the connection instead of downshifting.
                "finalmask": {
                    "quicParams": {
                        "congestion": "bbr",
                        "debug": False,
                        "disablePathMTUDiscovery": True,
                        "keepAlivePeriod": 6,
                        "maxIdleTimeout": 60,
                    }
                },
                "hysteriaSettings": {
                    "auth": server.auth_password,
                    "version": 2,
                },
                "tlsSettings": {
                    "alpn": ["h3"],
                    "enableSessionResumption": False,
                    "fingerprint": server.fingerprint,
                    # serverName is the decoy SNI; the cert the node actually
                    # presents is for cert_name, and that's what gets verified.
                    # Without this the client checks the cert against the decoy
                    # name, fails, and drops the connection before any traffic
                    # flows -- which is why this whole tier was dead.
                    "serverName": server.server_name,
                    **({"verifyPeerCertByName": server.cert_name} if server.cert_name else {}),
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

    # The Aeza node is a dedicated relay for blocklisted services (its own
    # outbounds below), not a general-purpose tier candidate. Left in the
    # regular selector it competes with much closer Selectel nodes for every
    # *unblocked* connection too -- leastPing has no notion of "only use this
    # one for Telegram", so ordinary browsing traffic would intermittently
    # detour through Stockholm for no reason, adding real latency across the
    # board rather than just where the relay is actually needed.
    for tier in _TIERS:
        tier_servers = [s for s in servers if s.tier == tier and "aeza" not in s.name.lower()]
        if not tier_servers:
            # Graceful degradation: if the whole non-relay side of a tier is
            # gone (an entire provider account can go dark at once -- this is
            # exactly how the Selectel mesh and, earlier, the whole Timeweb
            # fleet died), fall back to Aeza rather than leaving the tier with
            # nowhere to route. Clients connecting but nothing loading is worse
            # than everything running through the relay node.
            tier_servers = [s for s in servers if s.tier == tier and "aeza" in s.name.lower()]
        for i, server in enumerate(tier_servers):
            tag = f"{tier.upper()}-{i}"
            outbounds.append(_make_outbound(server, user_uuid, tag))
            tier_tags[tier].append(tag)

    # Selectel (our msk/lte hosting) enforces Roskomnadzor's blocklist at the
    # network level -- confirmed for both Telegram and the whole Meta family
    # (Instagram/Facebook/WhatsApp all time out via plain curl straight from a
    # Selectel node, no VPN involved). No amount of client-side protocol
    # trickery gets through that, since it's blocked before Xray ever sees the
    # packet. The one non-RU node (its name marks it as the relay) isn't
    # behind that block, so traffic to any blocklisted service gets pinned
    # there regardless of which tier the balancer would otherwise pick.
    blocked_relay_server = next((s for s in servers if "aeza" in s.name.lower() and s.transport == "tcp"), None)
    if blocked_relay_server:
        # Preserve the previously working VLESS/Reality settings. Enabling mux
        # here was followed by a reported Telegram connection regression.
        outbounds.append(_make_outbound(blocked_relay_server, user_uuid, "TG-RELAY"))

    # Reality/tcp can't carry raw UDP, and Instagram sends the bulk of its
    # traffic over QUIC (UDP:443) -- so the TCP relay alone leaves the app
    # hanging. Hysteria2 is UDP-native, and we run it on the same non-RU host,
    # so QUIC to a blocklisted service gets its own relay leg there.
    blocked_relay_udp_server = next(
        (s for s in servers if "aeza" in s.name.lower() and s.protocol == "hysteria2"), None
    )
    if blocked_relay_udp_server:
        outbounds.append(_make_outbound(blocked_relay_udp_server, user_uuid, "TG-RELAY-UDP"))

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
    if blocked_relay_server:
        # network: tcp only -- TG-RELAY is a Reality/tcp outbound, it cannot
        # carry raw UDP. Without this, a QUIC (UDP:443) attempt to instagram.com
        # matches on domain before the QUIC-block rule below ever sees it, gets
        # routed to a TCP-only outbound, and just hangs instead of failing fast
        # into the TCP fallback -- so the app's HTML/API shell loads fine but
        # media (the actual bulk of its traffic, sent over QUIC first) never
        # does. Leaving UDP unmatched here lets it fall through to that rule.
        routing_rules.append({"domain": _TELEGRAM_DOMAINS + _META_DOMAINS, "outboundTag": "TG-RELAY", "network": "tcp", "type": "field"})
        routing_rules.append({"ip": _TELEGRAM_CIDRS + _META_CIDRS, "outboundTag": "TG-RELAY", "network": "tcp", "type": "field"})

    if blocked_relay_udp_server:
        routing_rules.append({"domain": _TELEGRAM_DOMAINS + _META_DOMAINS, "outboundTag": "TG-RELAY-UDP", "network": "udp", "type": "field"})
        routing_rules.append({"ip": _TELEGRAM_CIDRS + _META_CIDRS, "outboundTag": "TG-RELAY-UDP", "network": "udp", "type": "field"})

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
            # leastLoad (matching the competitor's raw config) needs enough
            # burstObservatory health data to grade candidates before it will
            # route anything at all; when that data isn't there yet -- exactly
            # what an empty "connectivity" pre-check plus a flaky network
            # produces -- it fails closed instead of picking *something*, which
            # read as "connects but nothing loads" end to end. leastPing always
            # picks the fastest-responding candidate even with sparse data.
            "strategy": {"type": "leastPing"},
            "fallbackTag": _LOOPBACK_TAG[fallback] if fallback else "block",
        })

    # None of the Selectel tiers have a global IPv6 address -- only link-local
    # -- so any v6 destination that reaches a balancer is dead on arrival and
    # hangs rather than failing. Cutting v6 off here makes clients fall straight
    # back to v4, which does work. Anything that genuinely needs v6 (Telegram's
    # DCs, Meta) is already matched by the relay rules above and never gets here.
    routing_rules.append({"ip": ["::/0"], "outboundTag": "block", "type": "field"})

    # MSK/LTE are TCP-only (Reality/tcp, Reality/gRPC) -- they cannot carry raw
    # UDP. QUIC-heavy apps (Instagram, YouTube, anything on HTTP/3) send their
    # real traffic as UDP:443 first; routed into a TCP-only balancer that
    # traffic doesn't fail fast, it just hangs, and the app never falls back to
    # its own TLS-over-TCP path. Blocking QUIC outright forces that fallback
    # immediately, so it flows through the working Reality/TCP tunnel instead.
    # LLP (Hysteria2/QUIC-native) is unaffected: this only intercepts real
    # client traffic entering routing fresh, not the internal loopback re-entry
    # traffic matched by the inboundTag rules above.
    routing_rules.append({"network": "udp", "port": "443", "outboundTag": "block", "type": "field"})

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
                # Empty, not a Huawei/Google URL: a "connectivity" pre-check gate
                # that itself needs to succeed before any outbound is graded
                # healthy is one more thing that can be unreachable on a given
                # network, silently marking every outbound "down" and making the
                # balancer flap between them without ever settling. Matches the
                # competitor config confirmed working -- they leave it blank too.
                "connectivity": "",
                "destination": "https://www.gstatic.com/generate_204",
                "httpMethod": "GET",
                "interval": "1m",
                "sampling": 2,
                "timeout": "8s",
            },
            "subjectSelector": [tier.upper() for tier in _TIERS if tier_tags[tier]],
        }

    return config
