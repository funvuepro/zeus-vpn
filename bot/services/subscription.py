from decimal import Decimal
from datetime import datetime, timezone, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database.models import (
    Payment,
    PaymentStatus,
    Plan,
    ReferralStatus,
    ReferralTransaction,
    Subscription,
    SubscriptionStatus,
    User,
)
from bot.services.remnawave import remnawave
from bot.services.promo import record_usage

_MSK = timezone(timedelta(hours=3))


async def notify_user(telegram_id: int, text: str):
    pass  # replaced at startup in main.py


def _receipt(payment: Payment, plan: Plan, expires_at: datetime, devices: int, bonus_days: int = 0) -> str:
    now_msk = datetime.now(_MSK)
    exp_msk = expires_at.replace(tzinfo=timezone.utc).astimezone(_MSK)
    bonus_line = f"\n🎁 Бонусных дней применено: +{bonus_days}" if bonus_days > 0 else ""
    return (
        f"✅ <b>Оплата подтверждена</b>\n\n"
        f"📋 Тариф: {plan.name} ({plan.duration_days} дн.)\n"
        f"💰 Сумма: {round(float(payment.amount))} ₽\n"
        f"📅 Дата: {now_msk.strftime('%d.%m.%Y %H:%M')} МСК\n"
        f"🔑 ID заказа: #{payment.id}"
        f"{bonus_line}\n\n"
        f"📆 Подписка активна до: <b>{exp_msk.strftime('%d.%m.%Y')}</b>\n"
        f"📱 Устройств: {devices}\n\n"
        f"<i>Сохраните это сообщение как подтверждение оплаты.</i>"
    )


def _device_receipt(payment: Payment, count: int, total_devices: int) -> str:
    now_msk = datetime.now(_MSK)
    return (
        f"✅ <b>Оплата подтверждена</b>\n\n"
        f"📋 Услуга: +{count} устройств{'а' if 2 <= count <= 4 else ''}\n"
        f"💰 Сумма: {round(float(payment.amount))} ₽\n"
        f"📅 Дата: {now_msk.strftime('%d.%m.%Y %H:%M')} МСК\n"
        f"🔑 ID заказа: #{payment.id}\n\n"
        f"📱 Всего устройств: <b>{total_devices}</b>\n\n"
        f"<i>Сохраните это сообщение как подтверждение оплаты.</i>"
    )


async def activate_subscription(payment_id: int, session: AsyncSession):
    result = await session.execute(
        update(Payment)
        .where(Payment.id == payment_id, Payment.status == PaymentStatus.pending)
        .values(status=PaymentStatus.paid)
        .returning(Payment)
    )
    payment = result.scalar_one_or_none()
    if payment is None:
        return

    result = await session.execute(select(User).where(User.id == payment.user_id))
    user = result.scalar_one()

    result = await session.execute(select(Plan).where(Plan.id == payment.plan_id))
    plan = result.scalar_one()

    if getattr(payment, 'is_upgrade', False) and payment.devices_count:
        await _handle_upgrade(payment, user, session)
        return

    if plan.duration_days == 0:
        await _add_devices(payment, user, plan, session)
        return

    # Award referral bonus days BEFORE consuming them
    await _award_referral_bonus(payment, user, session)

    # Consume bonus days into subscription
    extra_days = user.bonus_days
    user.bonus_days = 0
    total_days = plan.duration_days + extra_days

    username = f"user_{user.telegram_id}"

    if not user.remnawave_uuid:
        sub_url, rw_uuid = await remnawave.create_user(username, total_days)
        user.remnawave_uuid = rw_uuid

        expires_at = datetime.now(timezone.utc) + timedelta(days=total_days)
        subscription = Subscription(
            user_id=user.id,
            plan_id=plan.id,
            devices_limit=getattr(payment, 'devices_count', None) or plan.devices_limit,
            expires_at=expires_at,
            status=SubscriptionStatus.active,
        )
        session.add(subscription)
        await session.flush()
        payment.subscription_id = subscription.id

        if payment.promo_code_id is not None:
            await record_usage(session, payment.promo_code_id, user.id)

        await session.commit()
        await _create_referral_tx(payment, user, session)

        await notify_user(user.telegram_id, _receipt(payment, plan, expires_at, subscription.devices_limit, extra_days))
        # Also send subscription URL for new users
        await notify_user(
            user.telegram_id,
            f"🔗 Ссылка на вашу подписку:\n<code>{sub_url}</code>\n\n"
            f"Нажмите «⚡️ Подключить VPN» в меню для инструкции по подключению.",
        )

    else:
        result = await session.execute(
            select(Subscription).where(
                Subscription.user_id == user.id,
                Subscription.status == SubscriptionStatus.active,
            )
        )
        existing_sub = result.scalar_one_or_none()
        if existing_sub:
            new_expires = existing_sub.expires_at + timedelta(days=total_days)
            existing_sub.expires_at = new_expires
            existing_sub.is_trial = False
            payment.subscription_id = existing_sub.id

            if payment.promo_code_id is not None:
                await record_usage(session, payment.promo_code_id, user.id)

            await session.commit()
            await _create_referral_tx(payment, user, session)
            await remnawave.extend_user(username, new_expires)
            bonus_notice = f" (+{extra_days} бонусных)" if extra_days > 0 else ""
            await notify_user(
                user.telegram_id,
                f"✅ Подписка DS-VPN продлена до {new_expires.strftime('%d.%m.%Y')}{bonus_notice}",
            )
        else:
            expires_at = datetime.now(timezone.utc) + timedelta(days=total_days)
            subscription = Subscription(
                user_id=user.id,
                plan_id=plan.id,
                devices_limit=getattr(payment, 'devices_count', None) or plan.devices_limit,
                expires_at=expires_at,
                status=SubscriptionStatus.active,
            )
            session.add(subscription)
            await session.flush()
            payment.subscription_id = subscription.id

            if payment.promo_code_id is not None:
                await record_usage(session, payment.promo_code_id, user.id)

            await session.commit()
            await _create_referral_tx(payment, user, session)

            bonus_notice = f"\n🎁 Применено бонусных дней: +{extra_days}" if extra_days > 0 else ""
            await notify_user(
                user.telegram_id,
                f"✅ <b>Оплата получена!</b>\n\n"
                f"Твоя ссылка DS-VPN:\n<code>{sub_url}</code>\n\n"
                f"Вставь её в приложение Hiddify или v2rayNG."
                f"{bonus_notice}",
            )


async def _handle_upgrade(payment: Payment, user: User, session: AsyncSession):
    result = await session.execute(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.status == SubscriptionStatus.active,
        )
    )
    sub = result.scalar_one_or_none()
    if not sub:
        await session.commit()
        await notify_user(user.telegram_id, "\u274c \u041d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u0430 \u0430\u043a\u0442\u0438\u0432\u043d\u0430\u044f \u043f\u043e\u0434\u043f\u0438\u0441\u043a\u0430.")
        return

    old_limit = sub.devices_limit
    sub.devices_limit = payment.devices_count
    payment.subscription_id = sub.id
    await session.commit()
    await _create_referral_tx(payment, user, session)
    await notify_user(
        user.telegram_id,
        f"\u2705 <b>\u0410\u043f\u0433\u0440\u0435\u0439\u0434 \u0443\u0441\u0442\u0440\u043e\u0439\u0441\u0442\u0432</b>\n\n"
        f"\U0001f4f1 \u0411\u044b\u043b\u043e: {old_limit} \u0443\u0441\u0442\u0440 \u2192 \u0421\u0442\u0430\u043b\u043e: {sub.devices_limit} \u0443\u0441\u0442\u0440\n"
        f"\U0001f4b0 \u0421\u0443\u043c\u043c\u0430: {round(float(payment.amount))} \u20bd\n\n"
        f"<i>\u0421\u043e\u0445\u0440\u0430\u043d\u0438\u0442\u0435 \u044d\u0442\u043e \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435 \u043a\u0430\u043a \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0438\u0435.</i>",
    )


async def _add_devices(payment: Payment, user: User, plan: Plan, session: AsyncSession):
    count = round(float(payment.amount) / float(plan.price))
    result = await session.execute(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.status == SubscriptionStatus.active,
        )
    )
    sub = result.scalar_one_or_none()
    if not sub:
        await session.commit()
        await notify_user(user.telegram_id, "❌ Не найдена активная подписка для добавления устройств.")
        return

    sub.devices_limit += count
    payment.subscription_id = sub.id
    await session.commit()
    await _create_referral_tx(payment, user, session)
    await notify_user(
        user.telegram_id,
        f"✅ Добавлено устройств: +{count}\nТеперь у тебя {sub.devices_limit} устройств.",
    )


async def _create_referral_tx(payment: Payment, user: User, session: AsyncSession):
    if not user.referred_by:
        return

    reward = (
        Decimal(payment.amount) * Decimal(str(settings.REFERRAL_PERCENT))
    ).quantize(Decimal("0.01"))
    ref_tx = ReferralTransaction(
        referrer_id=user.referred_by,
        payment_id=payment.id,
        amount=reward,
        status=ReferralStatus.pending,
    )
    session.add(ref_tx)
    await session.commit()

    result = await session.execute(select(User).where(User.id == user.referred_by))
    referrer = result.scalar_one_or_none()
    if referrer:
        await notify_user(referrer.telegram_id, f"💰 +{reward} ₽ зачислено на реферальный баланс!")


async def _award_referral_bonus(payment: Payment, user: User, session: AsyncSession):
    """Awards bonus days on first subscription purchase of a referred user."""
    if not user.referred_by:
        return

    # Check if this is the user's first paid payment
    result = await session.execute(
        select(func.count(Payment.id)).where(
            Payment.user_id == user.id,
            Payment.status == PaymentStatus.paid,
            Payment.id != payment.id,
        )
    )
    if (result.scalar_one() or 0) > 0:
        return  # Not first purchase

    # +10 days to friend (current user)
    user.bonus_days += 10

    # +5 days to referrer
    result = await session.execute(select(User).where(User.id == user.referred_by))
    referrer = result.scalar_one_or_none()
    if referrer:
        referrer.bonus_days += 5
        await notify_user(referrer.telegram_id, "🎁 +5 бонусных дней за приглашённого друга!")
