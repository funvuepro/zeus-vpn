from bot.database.models import VpnServer
from bot.services.xray_config import build_xray_config

USER_UUID = "11111111-1111-1111-1111-111111111111"


def _vless(tier: str, name: str, transport: str = "tcp", server_name: str = "max.ru") -> VpnServer:
    return VpnServer(
        name=name, ip="1.2.3.4", port=443, protocol="vless", transport=transport,
        public_key="pubkey", short_id="abcd1234", server_name=server_name,
        fingerprint="firefox", tier=tier, is_active=True,
    )


def _hysteria2(tier: str, name: str) -> VpnServer:
    return VpnServer(
        name=name, ip="5.6.7.8", port=10000, protocol="hysteria2",
        fingerprint="firefox", server_name="cdn.example.ru", auth_password="secret",
        tier=tier, is_active=True,
    )


def _balancer(config: dict, tag: str) -> dict:
    return next(b for b in config["routing"]["balancers"] if b["tag"] == tag)


def test_single_tier_has_one_balancer_and_no_loopback():
    servers = [_vless("msk", "msk-1")]
    config = build_xray_config(USER_UUID, servers)

    balancers = config["routing"]["balancers"]
    assert len(balancers) == 1
    assert balancers[0]["tag"] == "msk_balancer"
    assert "fallbackTag" not in balancers[0]
    assert not any(o["protocol"] == "loopback" for o in config["outbounds"])
    assert {"balancerTag": "msk_balancer", "type": "field", "network": "tcp,udp"} in config["routing"]["rules"]


def test_three_tier_cascade_chains_through_loopback_outbounds():
    servers = [
        _vless("msk", "msk-1"), _vless("msk", "msk-2"),
        _vless("lte", "lte-1", transport="grpc"),
        _hysteria2("llp", "llp-1"),
    ]
    config = build_xray_config(USER_UUID, servers)

    msk_balancer = _balancer(config, "msk_balancer")
    lte_balancer = _balancer(config, "lte_balancer")
    llp_balancer = _balancer(config, "llp_balancer")

    assert msk_balancer["selector"] == ["MSK-0", "MSK-1"]
    assert msk_balancer["fallbackTag"] == "LOOP-LTE"
    assert lte_balancer["selector"] == ["LTE-0"]
    assert lte_balancer["fallbackTag"] == "LOOP-LLP"
    assert llp_balancer["selector"] == ["LLP-0"]
    assert "fallbackTag" not in llp_balancer

    loopback_tags = {o["tag"]: o for o in config["outbounds"] if o["protocol"] == "loopback"}
    assert loopback_tags["LOOP-LTE"]["settings"]["inboundTag"] == "LTE-REROUTE"
    assert loopback_tags["LOOP-LLP"]["settings"]["inboundTag"] == "LLP-REROUTE"

    rules = config["routing"]["rules"]
    assert {"type": "field", "inboundTag": ["LTE-REROUTE"], "balancerTag": "lte_balancer"} in rules
    assert {"type": "field", "inboundTag": ["LLP-REROUTE"], "balancerTag": "llp_balancer"} in rules
    # the catch-all entry rule must point at the first tier (msk), not lte/llp
    assert {"balancerTag": "msk_balancer", "type": "field", "network": "tcp,udp"} in rules

    assert config["burstObservatory"]["subjectSelector"] == ["MSK", "LTE", "LLP"]


def test_missing_msk_tier_enters_at_lte():
    servers = [_vless("lte", "lte-1"), _hysteria2("llp", "llp-1")]
    config = build_xray_config(USER_UUID, servers)

    rules = config["routing"]["rules"]
    assert {"balancerTag": "lte_balancer", "type": "field", "network": "tcp,udp"} in rules
    assert not any(b["tag"] == "msk_balancer" for b in config["routing"]["balancers"])
    assert _balancer(config, "lte_balancer")["fallbackTag"] == "LOOP-LLP"


def test_grpc_outbound_authority_matches_server_name():
    config = build_xray_config(USER_UUID, [_vless("lte", "lte-1", transport="grpc", server_name="eh.vk.ru")])
    outbound = next(o for o in config["outbounds"] if o["tag"] == "LTE-0")
    assert outbound["streamSettings"]["grpcSettings"]["authority"] == "eh.vk.ru"
    assert outbound["streamSettings"]["grpcSettings"]["serviceName"] == "grpc"


def test_hysteria2_outbound_uses_happ_dialect():
    config = build_xray_config(USER_UUID, [_hysteria2("llp", "llp-1")])
    outbound = next(o for o in config["outbounds"] if o["tag"] == "LLP-0")
    assert outbound["protocol"] == "hysteria"
    assert outbound["streamSettings"]["hysteriaSettings"]["version"] == 2


def test_single_server_has_no_burst_observatory():
    config = build_xray_config(USER_UUID, [_vless("msk", "msk-1")])
    assert "burstObservatory" not in config


def test_telegram_traffic_is_pinned_to_the_aeza_relay():
    servers = [
        _vless("msk", "msk-1"),
        _vless("lte", "zeus-lte-aeza-tcp"),
        _vless("lte", "zeus-lte-aeza-grpc", transport="grpc"),
    ]
    config = build_xray_config(USER_UUID, servers)

    relay_outbounds = [o for o in config["outbounds"] if o["tag"] == "TG-RELAY"]
    assert len(relay_outbounds) == 1
    assert relay_outbounds[0]["settings"]["vnext"][0]["address"] == "1.2.3.4"

    rules = config["routing"]["rules"]
    telegram_domain_rule = next(r for r in rules if r.get("outboundTag") == "TG-RELAY" and "domain" in r)
    telegram_ip_rule = next(r for r in rules if r.get("outboundTag") == "TG-RELAY" and "ip" in r)
    assert "domain:telegram.org" in telegram_domain_rule["domain"]
    assert "91.108.4.0/22" in telegram_ip_rule["ip"]
    # Must not depend on a geo database the client's Xray build may not have --
    # an unresolvable geosite/geoip category can fail the whole routing config.
    assert not any("geosite:" in str(r.get("domain", [])) or "geoip:" in str(r.get("ip", [])) for r in rules)


def test_no_telegram_relay_rule_without_an_aeza_server():
    config = build_xray_config(USER_UUID, [_vless("msk", "msk-1"), _vless("lte", "lte-1")])
    assert not any(o["tag"] == "TG-RELAY" for o in config["outbounds"])
    assert not any(r.get("outboundTag") == "TG-RELAY" for r in config["routing"]["rules"])
