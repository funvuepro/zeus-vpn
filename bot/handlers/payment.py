from datetime import datetime, timezone

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Payment, PaymentProvider, Plan, Subscription, SubscriptionStatus, User
from bot.keyboards.inline import (
    get_price,
    order_confirm_keyboard,
    payment_formed_keyboard,
    S,
)
from bot.services.freekassa import create_payment_url as fk_payment_url
from bot.utils import smart_edit

router = Router()


@router.callback_query(F.data.startswith("order:"))
async def order_confirm(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    await callback.answer()
    parts = callback.data.split(":")
    plan_id = int(parts[1])
    devices = int(parts[2])
    plan = await session.get(Plan, plan_id)

    data = await state.get_data()
    discount = data.get("discount", 0)
    promo_str = data.get("promo_str", "")
    promo_applied = discount > 0

    total_raw = get_price(plan.duration_days, devices)
    final = max(total_raw - discount, 0)

    await state.update_data(plan_id=plan_id, devices=devices)

    price_line = f"└ 💲 К оплате: {final} ₽"
    if discount > 0:
        price_line = f"└ 💲 К оплате: {final} ₽ <s>{total_raw} ₽</s>"

    msg = (
        f"💎 <b>ПОДТВЕРЖДЕНИЕ ЗАКАЗА</b>\n\n"
        f"├ 📊 Тариф: 💎 {plan.duration_days} дн. · {devices} устр\n"
        f"├ 📱 Устройств: Стандарт ({devices})\n"
        f"{price_line}"
    )
    await smart_edit(callback, msg, order_confirm_keyboard(plan_id, devices, promo_applied, promo_str))


@router.callback_query(F.data.startswith("confirm_pay:"))
async def confirm_payment(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    await callback.answer()
    parts = callback.data.split(":")
    plan_id = int(parts[1])
    devices = int(parts[2])

    data = await state.get_data()
    promo_code_id = data.get("promo_code_id")
    discount = data.get("discount", 0)

    plan = await session.get(Plan, plan_id)
    user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))

    total_raw = get_price(plan.duration_days, devices)
    final = max(total_raw - discount, 0)

    payment = Payment(
        user_id=user.id,
        plan_id=plan.id,
        provider=PaymentProvider.freekassa,
        amount=final,
        promo_code_id=promo_code_id,
        devices_count=devices,
    )
    session.add(payment)
    await session.flush()

    pay_url = fk_payment_url(final, payment.id)
    await session.commit()

    msg = (
        f"💎 <b>ПЛАТЁЖ СФОРМИРОВАН</b>\n\n"
        f"├ 📊 Тариф: 💎 {plan.duration_days} дн. · {devices} устр\n"
        f"└ 💲 Сумма: {final} ₽\n\n"
        f"Нажмите кнопку ниже для оплаты. Ссылка активна в течение 10 минут."
    )
    await smart_edit(callback, msg, payment_formed_keyboard(pay_url))


def _get_sub_info(sub, plan):
    now = datetime.now(timezone.utc)
    started = sub.started_at
    if started and not started.tzinfo:
        started = started.replace(tzinfo=timezone.utc)
    expires = sub.expires_at
    if expires and not expires.tzinfo:
        expires = expires.replace(tzinfo=timezone.utc)
    total = max(1, (expires - started).days) if started else plan.duration_days
    remaining = max(0, (expires - now).days)
    return total, remaining


@router.callback_query(F.data.startswith("upgrade_to:"))
async def upgrade_confirm(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    new_devices = int(callback.data.split(":")[1])

    user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
    sub = await session.scalar(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.status == SubscriptionStatus.active,
        ).order_by(Subscription.expires_at.desc())
    )
    if not sub:
        await callback.answer("Нет активной подписки", show_alert=True)
        return

    plan = await session.get(Plan, sub.plan_id)
    total, remaining = _get_sub_info(sub, plan)

    cur_price = get_price(plan.duration_days, sub.devices_limit)
    new_price = get_price(plan.duration_days, new_devices)
    upgrade_cost = max(1, round((new_price - cur_price) * remaining / total))

    msg = (
        f"➕ <b>ДОБАВЛЕНИЕ УСТРОЙСТВ</b>\n\n"
        f"├ 📱 Сейчас: {sub.devices_limit} устр\n"
        f"├ 📱 Новый лимит: {new_devices} устр\n"
        f"├ ⏳ Осталось: {remaining} дней\n"
        f"└ 💲 Доплата: {upgrade_cost} ₽"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ Оплатить {upgrade_cost} ₽", callback_data=f"confirm_upgrade:{new_devices}", style=S)],
        [InlineKeyboardButton(text="◀ Назад", callback_data="add_devices")],
    ])
    await smart_edit(callback, msg, keyboard)


@router.callback_query(F.data.startswith("confirm_upgrade:"))
async def confirm_upgrade(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    new_devices = int(callback.data.split(":")[1])

    user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
    sub = await session.scalar(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.status == SubscriptionStatus.active,
        ).order_by(Subscription.expires_at.desc())
    )
    if not sub:
        await callback.answer("Нет активной подписки", show_alert=True)
        return

    plan = await session.get(Plan, sub.plan_id)
    total, remaining = _get_sub_info(sub, plan)

    cur_price = get_price(plan.duration_days, sub.devices_limit)
    new_price = get_price(plan.duration_days, new_devices)
    upgrade_cost = max(1, round((new_price - cur_price) * remaining / total))

    payment = Payment(
        user_id=user.id,
        plan_id=plan.id,
        provider=PaymentProvider.freekassa,
        amount=upgrade_cost,
        devices_count=new_devices,
        is_upgrade=True,
    )
    session.add(payment)
    await session.flush()

    pay_url = fk_payment_url(upgrade_cost, payment.id)
    await session.commit()

    msg = (
        f"💎 <b>ПЛАТЁЖ СФОРМИРОВАН</b>\n\n"
        f"├ 📱 Апгрейд: {sub.devices_limit} → {new_devices} устр\n"
        f"└ 💲 Сумма: {upgrade_cost} ₽\n\n"
        f"Нажмите кнопку ниже для оплаты."
    )
    await smart_edit(callback, msg, payment_formed_keyboard(pay_url))
