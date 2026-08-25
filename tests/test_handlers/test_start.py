from decimal import Decimal
from bot.database.models import User
from bot.handlers.start import build_menu_text


async def test_build_menu_text_shows_balance_and_devices(db_session):
    user = User(telegram_id=1, balance=Decimal("42.50"), devices_limit=2, access_active=True)
    text = await build_menu_text(user, db_session)
    assert "Zeus VPN" in text
    assert "42.5" in text or "42.50" in text
    assert "2" in text


async def test_build_menu_text_shows_disabled_access(db_session):
    user = User(telegram_id=1, balance=Decimal("0.00"), devices_limit=1, access_active=False)
    text = await build_menu_text(user, db_session)
    assert "отключ" in text.lower()


async def test_build_menu_text_shows_tariff_line(db_session):
    user = User(telegram_id=1, balance=Decimal("100.00"), devices_limit=3, access_active=True)
    text = await build_menu_text(user, db_session)
    assert "тариф" in text.lower()
    assert "3 устр" in text
