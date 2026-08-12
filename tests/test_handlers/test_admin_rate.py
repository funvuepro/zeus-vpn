from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from bot.database.models import User
from bot.handlers.admin import adm_set_rate_input, AdminStates


async def test_adm_set_rate_input_updates_rate(db_session):
    admin = User(telegram_id=999, username="root", is_admin=True)
    db_session.add(admin)
    await db_session.commit()

    message = MagicMock()
    message.from_user.id = 999
    message.text = "2.50"
    message.answer = AsyncMock()

    state = AsyncMock()
    state.get_data = AsyncMock(return_value={})

    await adm_set_rate_input(message, db_session, state)

    from bot.services.balance import get_daily_rate_per_device
    rate = await get_daily_rate_per_device(db_session)
    assert rate == Decimal("2.50")
    message.answer.assert_called_once()
