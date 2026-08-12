# tests/test_handlers/test_about.py
from bot.handlers.about import _PRIVACY, _TERMS, _TERMS_ACCEPT_TEXT


def test_legal_texts_use_new_brand_and_provider():
    for text in (_PRIVACY, _TERMS, _TERMS_ACCEPT_TEXT):
        assert "DS-VPN" not in text
        assert "Zeus VPN" in text
    assert "FreeKassa" not in _PRIVACY
    assert "CryptoBot" not in _PRIVACY
    assert "ЮKassa" in _PRIVACY
    assert "@ds_vpnsupport" not in _PRIVACY
    assert "@zeus_vpnsupport" in _PRIVACY
