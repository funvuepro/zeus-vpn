import pytest
from datetime import datetime, timedelta, timezone

from bot.database.models import PromoCode, PromoCodeUsage, User
from bot.services.promo import validate_promo, record_usage


async def _make_user(session, telegram_id=111):
    user = User(telegram_id=telegram_id, username="u")
    session.add(user)
    await session.flush()
    return user


async def _make_promo(session, code="SAVE100", amount=100, expires_at=None, is_active=True):
    promo = PromoCode(code=code, amount=amount, expires_at=expires_at, is_active=is_active)
    session.add(promo)
    await session.flush()
    return promo


async def test_validate_success(db_session):
    user = await _make_user(db_session)
    promo = await _make_promo(db_session, expires_at=datetime.now(timezone.utc) + timedelta(days=10))
    result, err = await validate_promo(db_session, "SAVE100", user.id)
    assert err is None
    assert result.id == promo.id


async def test_validate_lowercased_input(db_session):
    user = await _make_user(db_session)
    await _make_promo(db_session)
    result, err = await validate_promo(db_session, "save100", user.id)
    assert err is None
    assert result is not None


async def test_validate_not_found(db_session):
    user = await _make_user(db_session)
    result, err = await validate_promo(db_session, "NOTEXIST", user.id)
    assert result is None
    assert "не найден" in err


async def test_validate_inactive(db_session):
    user = await _make_user(db_session)
    await _make_promo(db_session, is_active=False)
    result, err = await validate_promo(db_session, "SAVE100", user.id)
    assert result is None
    assert "не найден" in err


async def test_validate_expired(db_session):
    user = await _make_user(db_session)
    await _make_promo(db_session, expires_at=datetime.now(timezone.utc) - timedelta(days=1))
    result, err = await validate_promo(db_session, "SAVE100", user.id)
    assert result is None
    assert "истёк" in err


async def test_validate_already_used(db_session):
    user = await _make_user(db_session)
    promo = await _make_promo(db_session, expires_at=datetime.now(timezone.utc) + timedelta(days=10))
    db_session.add(PromoCodeUsage(promo_code_id=promo.id, user_id=user.id))
    await db_session.flush()
    result, err = await validate_promo(db_session, "SAVE100", user.id)
    assert result is None
    assert "использовал" in err


async def test_validate_no_expiry(db_session):
    user = await _make_user(db_session)
    await _make_promo(db_session, expires_at=None)
    result, err = await validate_promo(db_session, "SAVE100", user.id)
    assert err is None


async def test_record_usage(db_session):
    user = await _make_user(db_session)
    promo = await _make_promo(db_session)
    await record_usage(db_session, promo.id, user.id)
    await db_session.flush()
    from sqlalchemy import select
    row = await db_session.scalar(
        select(PromoCodeUsage).where(
            PromoCodeUsage.promo_code_id == promo.id,
            PromoCodeUsage.user_id == user.id,
        )
    )
    assert row is not None
