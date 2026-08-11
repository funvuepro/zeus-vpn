from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from contextlib import asynccontextmanager

from bot.database.models import AppSettings, User
import bot.scheduler.tasks as tasks


def _mock_bot():
    bot = AsyncMock()
    return bot


class MockAsyncSessionLocal:
    """Context manager that wraps a session without closing it."""
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Don't close the session - let the fixture handle it
        return None


async def test_daily_billing_deducts_balance_for_active_users(db_session):
    db_session.add(AppSettings(id=1, daily_rate_per_device=Decimal("1.00")))
    user = User(telegram_id=700, username="u1", balance=Decimal("10.00"), devices_limit=1, access_active=True)
    db_session.add(user)
    await db_session.commit()

    bot = _mock_bot()
    with patch.object(tasks, "_get_bot", AsyncMock(return_value=bot)), \
         patch.object(tasks, "AsyncSessionLocal", lambda: MockAsyncSessionLocal(db_session)):
        await tasks.run_daily_billing()

    await db_session.refresh(user)
    assert user.balance == Decimal("9.00")


async def test_daily_billing_warns_one_day_before_zero(db_session):
    db_session.add(AppSettings(id=1, daily_rate_per_device=Decimal("1.00")))
    user = User(telegram_id=701, username="u2", balance=Decimal("1.00"), devices_limit=1, access_active=True)
    db_session.add(user)
    await db_session.commit()

    bot = _mock_bot()
    with patch.object(tasks, "_get_bot", AsyncMock(return_value=bot)), \
         patch.object(tasks, "AsyncSessionLocal", lambda: MockAsyncSessionLocal(db_session)):
        await tasks.run_daily_billing()

    await db_session.refresh(user)
    assert user.balance == Decimal("0.00")
    assert user.grace_started_at is not None
    assert bot.send_message.await_count == 1


async def test_daily_billing_disables_access_after_grace_expires(db_session):
    db_session.add(AppSettings(id=1, daily_rate_per_device=Decimal("1.00")))
    user = User(
        telegram_id=702, username="u3", balance=Decimal("0.00"), devices_limit=1,
        access_active=True, grace_started_at=datetime.now(timezone.utc) - timedelta(hours=25),
        remnawave_uuid="uuid-702",
    )
    db_session.add(user)
    await db_session.commit()

    bot = _mock_bot()
    with patch.object(tasks, "_get_bot", AsyncMock(return_value=bot)), \
         patch.object(tasks, "AsyncSessionLocal", lambda: MockAsyncSessionLocal(db_session)), \
         patch.object(tasks, "remnawave") as mock_remnawave:
        mock_remnawave.disable_user = AsyncMock()
        await tasks.run_daily_billing()
        mock_remnawave.disable_user.assert_called_once_with("uuid-702")

    await db_session.refresh(user)
    assert user.access_active is False


async def test_daily_billing_skips_inactive_users(db_session):
    db_session.add(AppSettings(id=1, daily_rate_per_device=Decimal("1.00")))
    user = User(telegram_id=703, username="u4", balance=Decimal("5.00"), devices_limit=1, access_active=False)
    db_session.add(user)
    await db_session.commit()

    bot = _mock_bot()
    with patch.object(tasks, "_get_bot", AsyncMock(return_value=bot)), \
         patch.object(tasks, "AsyncSessionLocal", lambda: MockAsyncSessionLocal(db_session)):
        await tasks.run_daily_billing()

    await db_session.refresh(user)
    assert user.balance == Decimal("5.00")  # untouched, access already inactive
