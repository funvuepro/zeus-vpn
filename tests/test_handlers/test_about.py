# tests/test_handlers/test_about.py
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from bot.database.models import User
from bot.handlers.about import (
    _PRIVACY,
    _TERMS,
    _TERMS_ACCEPT_TEXT,
    REMNAWAVE_EXPIRE_DAYS,
    accept_terms_handler,
)


def test_legal_texts_use_new_brand_and_provider():
    for text in (_PRIVACY, _TERMS, _TERMS_ACCEPT_TEXT):
        assert "DS-VPN" not in text
        assert "Zeus VPN" in text
    assert "FreeKassa" not in _PRIVACY
    assert "CryptoBot" not in _PRIVACY
    assert "ЮKassa" in _PRIVACY
    assert "@ds_vpnsupport" not in _PRIVACY
    assert "@zeus_vpnsupport" in _PRIVACY


def _accept_terms_callback(telegram_id: int) -> MagicMock:
    callback = MagicMock()
    callback.from_user.id = telegram_id
    callback.answer = AsyncMock()
    return callback


async def test_accept_terms_extends_existing_remnawave_user(db_session):
    # A user provisioned before the far-future expiry policy shipped already
    # has a remnawave_uuid with a near-term expireAt; re-accepting terms must
    # still push their Remnawave expiry out, not skip them because they
    # already have a uuid.
    user = User(telegram_id=800, username="oldie", remnawave_uuid="uuid-old")
    db_session.add(user)
    await db_session.commit()

    with patch("bot.handlers.about.remnawave") as mock_remnawave, \
         patch("bot.handlers.about.send_section", new=AsyncMock()):
        mock_remnawave.extend_user = AsyncMock()
        mock_remnawave.create_user = AsyncMock()
        await accept_terms_handler(_accept_terms_callback(800), db_session)

        mock_remnawave.extend_user.assert_called_once()
        call_username, call_expire_at = mock_remnawave.extend_user.call_args[0]
        assert call_username == "user_800"
        expected = datetime.now(timezone.utc) + timedelta(days=REMNAWAVE_EXPIRE_DAYS)
        assert abs((call_expire_at - expected).total_seconds()) < 5
        mock_remnawave.create_user.assert_not_called()

    await db_session.refresh(user)
    assert user.remnawave_uuid == "uuid-old"


async def test_accept_terms_provisions_new_remnawave_user(db_session):
    user = User(telegram_id=801, username="newbie")
    db_session.add(user)
    await db_session.commit()

    with patch("bot.handlers.about.remnawave") as mock_remnawave, \
         patch("bot.handlers.about.send_section", new=AsyncMock()):
        mock_remnawave.create_user = AsyncMock(return_value=("https://sub.example/xyz", "uuid-new"))
        mock_remnawave.extend_user = AsyncMock()
        await accept_terms_handler(_accept_terms_callback(801), db_session)

        mock_remnawave.create_user.assert_called_once_with("user_801", expire_days=REMNAWAVE_EXPIRE_DAYS)
        mock_remnawave.extend_user.assert_not_called()

    await db_session.refresh(user)
    assert user.remnawave_uuid == "uuid-new"
    assert user.terms_accepted is True
