import os

def test_settings_has_yookassa_and_no_legacy_providers(monkeypatch):
    monkeypatch.setenv("YOOKASSA_SHOP_ID", "shop_123")
    monkeypatch.setenv("YOOKASSA_SECRET_KEY", "secret_abc")
    from bot.config import Settings
    s = Settings()
    assert s.YOOKASSA_SHOP_ID == "shop_123"
    assert s.YOOKASSA_SECRET_KEY == "secret_abc"
    assert s.MIN_TOPUP_RUB == 100.0
    assert not hasattr(s, "CRYPTOBOT_TOKEN")
    assert not hasattr(s, "LAVA_API_KEY")
    assert not hasattr(s, "FREEKASSA_SHOP_ID")
    assert not hasattr(s, "REFERRAL_PERCENT")
