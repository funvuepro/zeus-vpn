from decimal import Decimal
from bot.database.models import User
from bot.handlers.start import build_menu_text


def test_build_menu_text_shows_balance_and_devices():
    user = User(telegram_id=1, balance=Decimal("42.50"), devices_limit=2, access_active=True)
    text = build_menu_text(user)
    assert "Zeus VPN" in text
    assert "42.5" in text or "42.50" in text
    assert "2" in text


def test_build_menu_text_shows_disabled_access():
    user = User(telegram_id=1, balance=Decimal("0.00"), devices_limit=1, access_active=False)
    text = build_menu_text(user)
    assert "отключ" in text.lower()
