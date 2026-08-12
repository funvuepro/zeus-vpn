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


def test_webhook_insecure_dev_defaults_to_false():
    from bot.config import Settings
    assert Settings().WEBHOOK_INSECURE_DEV is False


def test_build_uvicorn_kwargs_refuses_plain_http_by_default():
    import pytest
    from types import SimpleNamespace
    from bot.main import build_uvicorn_kwargs

    s = SimpleNamespace(SSL_CERT_PATH="", SSL_KEY_PATH="", WEBHOOK_INSECURE_DEV=False)
    with pytest.raises(RuntimeError, match="without TLS"):
        build_uvicorn_kwargs(s)


def test_build_uvicorn_kwargs_binds_loopback_in_insecure_dev_mode():
    from types import SimpleNamespace
    from bot.main import build_uvicorn_kwargs

    s = SimpleNamespace(SSL_CERT_PATH="", SSL_KEY_PATH="", WEBHOOK_INSECURE_DEV=True)
    kwargs = build_uvicorn_kwargs(s)
    assert kwargs["host"] == "127.0.0.1"
    assert "ssl_certfile" not in kwargs


def test_build_uvicorn_kwargs_uses_tls_when_configured():
    from types import SimpleNamespace
    from bot.main import build_uvicorn_kwargs

    s = SimpleNamespace(SSL_CERT_PATH="/certs/f.pem", SSL_KEY_PATH="/certs/k.pem", WEBHOOK_INSECURE_DEV=False)
    kwargs = build_uvicorn_kwargs(s)
    assert kwargs["host"] == "0.0.0.0"
    assert kwargs["ssl_certfile"] == "/certs/f.pem"
    assert kwargs["ssl_keyfile"] == "/certs/k.pem"
