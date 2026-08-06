from datetime import datetime, timezone, timedelta

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Plan, Subscription, SubscriptionStatus, User
from bot.handlers.start import build_menu_text
from bot.keyboards.inline import (
    PRICE_TABLE,
    back_to_menu_keyboard,
    connect_vpn_keyboard,
    main_menu_keyboard,
    support_keyboard,
    upgrade_devices_keyboard,
)
from bot.services.remnawave import remnawave
from bot.utils import send_section, smart_edit

router = Router()

MSK = timezone(timedelta(hours=3))


@router.callback_query(F.data == "connect_vpn")
async def connect_vpn_handler(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
    sub = None
    if user:
        sub = await session.scalar(
            select(Subscription).where(
                Subscription.user_id == user.id,
                Subscription.status == SubscriptionStatus.active,
            ).order_by(Subscription.expires_at.desc())
        )

    if sub:
        sub_url = ""
        try:
            sub_url = await remnawave.get_subscription_url(f"user_{user.telegram_id}")
        except Exception:
            pass

        expires = sub.expires_at.replace(tzinfo=timezone.utc).astimezone(MSK)
        if sub_url:
            text = (
                "⚡️ <b>ПОДКЛЮЧИТЬ VPN</b>\n\n"
                f"✅ Подписка активна до {expires.strftime('%d.%m.%Y')}\n"
                f"📱 Устройств: <b>{sub.devices_limit}</b>\n\n"
                "📋 <b>Ссылка подписки:</b>\n"
                f"<code>{sub_url}</code>\n\n"
                "Скопируй ссылку и вставь в:\n"
                "• <b>Hiddify</b> (рекомендуем)\n"
                "• <b>v2rayNG</b> / <b>Happ</b>"
            )
        else:
            text = (
                "⚡️ <b>ПОДКЛЮЧИТЬ VPN</b>\n\n"
                f"✅ Подписка активна до {expires.strftime('%d.%m.%Y')}\n\n"
                "⚠️ Не удалось загрузить ссылку подписки.\n"
                "Попробуй позже или обратись в поддержку."
            )
    else:
        text = (
            "⚡️ <b>ПОДКЛЮЧИТЬ VPN</b>\n\n"
            "❌ У тебя нет активной подписки.\n\n"
            "Купи подписку, чтобы получить ссылку для подключения к DS-VPN."
        )

    await smart_edit(callback, text, connect_vpn_keyboard(has_sub=sub is not None))


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))

    if not user or not user.terms_accepted:
        from bot.handlers.about import get_terms_accept_text
        from bot.keyboards.inline import terms_accept_keyboard
        await smart_edit(callback, get_terms_accept_text(), terms_accept_keyboard())
        return

    sub = await session.scalar(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.status == SubscriptionStatus.active,
        ).order_by(Subscription.expires_at.desc())
    )
    await send_section(
        callback,
        "main",
        build_menu_text(user, sub),
        main_menu_keyboard(has_sub=sub is not None),
    )


@router.callback_query(F.data == "support")
async def support(callback: CallbackQuery):
    await callback.answer()
    await send_section(
        callback,
        "support",
        "🆘 <b>Поддержка DS-VPN</b>\n\n"
        "Возникли вопросы или проблемы с подключением?\n"
        "Напиши нам — поможем разобраться.\n\n"
        "⏱ Время ответа: до 24 часов.",
        support_keyboard(),
    )


@router.callback_query(F.data == "add_devices")
async def add_devices(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return

    sub = await session.scalar(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.status == SubscriptionStatus.active,
        )
    )
    if not sub:
        await callback.answer("Нет активной подписки", show_alert=True)
        return

    plan = await session.get(Plan, sub.plan_id)

    if plan.duration_days not in PRICE_TABLE:
        await smart_edit(
            callback,
            "➕ <b>Добавить устройства</b>\n\n"
            "Эта опция доступна только для платных подписок.",
            InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💎 Купить подписку", callback_data="buy_subscription")],
                [InlineKeyboardButton(text="◀ Назад", callback_data="connect_vpn")],
            ]),
        )
        return

    if sub.devices_limit >= 10:
        await smart_edit(
            callback,
            "➕ <b>Добавить устройства</b>\n\n"
            "У вас максимальный лимит (10 устройств).",
            InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀ Назад", callback_data="connect_vpn")],
            ]),
        )
        return

    now = datetime.now(timezone.utc)
    started = sub.started_at
    if started and not started.tzinfo:
        started = started.replace(tzinfo=timezone.utc)
    expires = sub.expires_at
    if expires and not expires.tzinfo:
        expires = expires.replace(tzinfo=timezone.utc)
    total = max(1, (expires - started).days) if started else plan.duration_days
    remaining = max(0, (expires - now).days)

    msg = (
        f"➕ <b>ДОБАВИТЬ УСТРОЙСТВА</b>\n\n"
        f"├ 📊 Подписка: {plan.duration_days} дн.\n"
        f"├ 📱 Сейчас: {sub.devices_limit} устр\n"
        f"└ ⏳ Осталось: {remaining} дней\n\n"
        f"Выберите новый лимит:"
    )
    await smart_edit(callback, msg, upgrade_devices_keyboard(plan.duration_days, sub.devices_limit, remaining, total))
