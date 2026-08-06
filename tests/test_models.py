import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from bot.database.models import User, Plan, Subscription, Payment, SubscriptionStatus, PaymentProvider, PaymentStatus

async def test_create_user(db_session):
    user = User(telegram_id=123456789, username="testuser")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.id is not None
    assert user.telegram_id == 123456789
    assert user.is_banned is False

async def test_referral_link(db_session):
    referrer = User(telegram_id=111, username="referrer")
    db_session.add(referrer)
    await db_session.commit()

    referred = User(telegram_id=222, username="referred", referred_by=referrer.id)
    db_session.add(referred)
    await db_session.commit()
    await db_session.refresh(referred)

    assert referred.referred_by == referrer.id

async def test_create_plan(db_session):
    plan = Plan(name="Стандарт", devices_limit=3, duration_days=30, price=Decimal("249.00"))
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(plan)
    assert plan.id is not None
    assert plan.is_active is True
