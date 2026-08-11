from datetime import datetime, timezone, timedelta

from sqlalchemy import select

from bot.database.models import User
from bot.database.session import AsyncSessionLocal
from bot.services.balance import get_daily_rate_per_device, calculate_daily_charge
from bot.services.remnawave import remnawave

GRACE_PERIOD = timedelta(hours=24)


async def _get_bot():
    from bot.main import _bot_instance
    return _bot_instance


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def run_daily_billing():
    async with AsyncSessionLocal() as session:
        bot = await _get_bot()
        now = datetime.now(timezone.utc)
        daily_rate = await get_daily_rate_per_device(session)

        result = await session.execute(select(User).where(User.access_active == True))
        users = result.scalars().all()

        for user in users:
            charge = calculate_daily_charge(daily_rate, user.devices_limit)
            user.balance -= charge

            if 0 < user.balance <= charge:
                try:
                    await bot.send_message(
                        user.telegram_id,
                        "⚡ Баланс скоро закончится, пополните — /start",
                    )
                except Exception:
                    pass

            if user.balance <= 0:
                if user.grace_started_at is None:
                    user.grace_started_at = now
                    try:
                        await bot.send_message(
                            user.telegram_id,
                            "⚡ Баланс исчерпан. 24 часа на пополнение, иначе доступ будет отключён.",
                        )
                    except Exception:
                        pass
                elif now - _aware(user.grace_started_at) >= GRACE_PERIOD:
                    user.access_active = False
                    if user.remnawave_uuid:
                        try:
                            await remnawave.disable_user(user.remnawave_uuid)
                        except Exception:
                            pass
                    try:
                        await bot.send_message(
                            user.telegram_id,
                            "❌ Доступ к Zeus VPN отключён. Пополните баланс — /start",
                        )
                    except Exception:
                        pass

        await session.commit()
