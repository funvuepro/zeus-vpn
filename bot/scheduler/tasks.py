from datetime import datetime, timezone, timedelta

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select

from bot.database.models import Subscription, SubscriptionStatus, User
from bot.database.session import AsyncSessionLocal
from bot.services.remnawave import remnawave


async def _get_bot():
    from bot.main import _bot_instance
    return _bot_instance


async def notify_expiring_subscriptions():
    async with AsyncSessionLocal() as session:
        bot = await _get_bot()
        now = datetime.now(timezone.utc)

        for days_before in [7, 3]:
            window_start = now + timedelta(days=days_before) - timedelta(hours=1)
            window_end = now + timedelta(days=days_before) + timedelta(hours=1)
            result = await session.execute(
                select(Subscription, User)
                .join(User, User.id == Subscription.user_id)
                .where(
                    Subscription.status == SubscriptionStatus.active,
                    Subscription.is_trial == False,
                    Subscription.expires_at.between(window_start, window_end),
                )
            )
            for sub, user in result.all():
                try:
                    await bot.send_message(
                        user.telegram_id,
                        f"⚠️ Подписка DS-VPN истекает через <b>{days_before} дней</b> "
                        f"({sub.expires_at.strftime('%d.%m.%Y')}).\n\n"
                        f"Продли сейчас — /start",
                        parse_mode="HTML",
                    )
                except Exception:
                    pass


async def notify_trial_expiring():
    async with AsyncSessionLocal() as session:
        bot = await _get_bot()
        now = datetime.now(timezone.utc)
        window_start = now + timedelta(hours=23)
        window_end = now + timedelta(hours=25)
        result = await session.execute(
            select(Subscription, User)
            .join(User, User.id == Subscription.user_id)
            .where(
                Subscription.status == SubscriptionStatus.active,
                Subscription.is_trial == True,
                Subscription.trial_notified == False,
                Subscription.expires_at.between(window_start, window_end),
            )
        )
        rows = result.all()
        for sub, user in rows:
            try:
                await bot.send_message(
                    user.telegram_id,
                    "⏰ <b>Ваш пробный период DS-VPN заканчивается!</b>\n\n"
                    "До окончания осталось менее 24 часов.\n\n"
                    "Не теряйте доступ к стабильному VPN — купите подписку прямо сейчас и сохраните все настройки.",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="💎 Купить подписку", callback_data="buy_subscription")],
                    ]),
                )
                sub.trial_notified = True
            except Exception:
                pass
        if rows:
            await session.commit()


async def deactivate_expired_subscriptions():
    async with AsyncSessionLocal() as session:
        bot = await _get_bot()
        now = datetime.now(timezone.utc)
        result = await session.execute(
            select(Subscription, User)
            .join(User, User.id == Subscription.user_id)
            .where(
                Subscription.status == SubscriptionStatus.active,
                Subscription.expires_at < now,
            )
        )
        rows = result.all()
        for sub, user in rows:
            sub.status = SubscriptionStatus.expired
            try:
                if user.remnawave_uuid:
                    await remnawave.disable_user(user.remnawave_uuid)
            except Exception:
                pass
            try:
                await bot.send_message(
                    user.telegram_id,
                    "❌ Твоя подписка DS-VPN истекла. Доступ отключён.\n\nВосстанови: /start",
                )
            except Exception:
                pass
        if rows:
            await session.commit()
