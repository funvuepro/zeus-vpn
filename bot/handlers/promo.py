from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Plan, User
from bot.keyboards.inline import order_confirm_keyboard, get_price
from bot.services.promo import validate_promo
from bot.services.promo_admin import create_promo, delete_promo, list_promos
from bot.utils import smart_edit

router = Router()


class PromoStates(StatesGroup):
    waiting_for_code = State()


def _require_admin(user: User) -> bool:
    return user.is_admin


@router.message(Command("newpromo"))
async def cmd_new_promo(message: Message, session: AsyncSession):
    user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
    if not user or not _require_admin(user):
        return
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("Использование: /newpromo КОД СУММА [ГГГГ-ММ-ДД]")
        return
    code = parts[1].upper()
    try:
        amount = int(parts[2])
    except ValueError:
        await message.answer("Сумма должна быть числом")
        return
    expires_str = parts[3] if len(parts) > 3 else None
    try:
        promo = await create_promo(session, code, amount, expires_str)
        await session.commit()
        exp = promo.expires_at.strftime("%d.%m.%Y") if promo.expires_at else "бессрочно"
        await message.answer(f"✅ Промокод <b>{promo.code}</b> создан\nСкидка: {promo.amount} ₽\nДействует: {exp}", parse_mode="HTML")
    except ValueError as e:
        await message.answer(str(e))


@router.message(Command("listpromos"))
async def cmd_list_promos(message: Message, session: AsyncSession):
    user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
    if not user or not _require_admin(user):
        return
    promos, counts = await list_promos(session)
    if not promos:
        await message.answer("Нет активных промокодов")
        return
    lines2 = []
    for p in promos:
        exp = p.expires_at.strftime("%d.%m.%Y") if p.expires_at else "∞"
        used = counts.get(p.id, 0)
        lines2.append(f"<b>{p.code}</b> — {p.amount} ₽, до {exp}, использований: {used}")
    await message.answer("\n".join(lines2), parse_mode="HTML")


@router.message(Command("deletepromo"))
async def cmd_delete_promo(message: Message, session: AsyncSession):
    user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
    if not user or not _require_admin(user):
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /deletepromo КОД")
        return
    code = parts[1].upper()
    deleted = await delete_promo(session, code)
    await session.commit()
    if deleted:
        await message.answer(f"✅ Промокод <b>{code}</b> деактивирован", parse_mode="HTML")
    else:
        await message.answer(f"❌ Промокод <b>{code}</b> не найден", parse_mode="HTML")


@router.callback_query(F.data.startswith("promo_apply_order:"))
async def promo_apply_order(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    parts = callback.data.split(":")
    plan_id = int(parts[1])
    devices = int(parts[2])
    await state.update_data(plan_id=plan_id, devices=devices)
    await state.set_state(PromoStates.waiting_for_code)
    await smart_edit(callback, "🏷 Введи промокод:")


@router.callback_query(F.data.startswith("promo_cancel_order:"))
async def promo_cancel_order(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    await callback.answer()
    parts = callback.data.split(":")
    plan_id = int(parts[1])
    devices = int(parts[2])
    await state.update_data(promo_code_id=None, discount=0, promo_str="")

    plan = await session.get(Plan, plan_id)
    final = get_price(plan.duration_days, devices)

    msg = (
        f"💎 <b>ПОДТВЕРЖДЕНИЕ ЗАКАЗА</b>\n\n"
        f"├ 📊 Тариф: 💎 {plan.duration_days} дн. · {devices} устр\n"
        f"├ 📱 Устройств: Стандарт ({devices})\n"
        f"└ 💲 К оплате: {final} ₽"
    )
    await smart_edit(callback, msg, order_confirm_keyboard(plan_id, devices))


@router.message(PromoStates.waiting_for_code)
async def promo_code_input(message: Message, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    plan_id = data.get("plan_id")
    devices = data.get("devices", 1)

    user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
    promo, error = await validate_promo(session, message.text.strip(), user.id)

    if error:
        await message.answer(error)
        await state.set_state(None)
        return

    await state.set_state(None)
    await state.update_data(promo_code_id=promo.id, discount=promo.amount, promo_str=promo.code)

    plan = await session.get(Plan, plan_id)
    total_raw = get_price(plan.duration_days, devices)
    final = max(total_raw - promo.amount, 0)

    msg = (
        f"✅ Промокод <b>{promo.code}</b> применён!\n\n"
        f"💎 <b>ПОДТВЕРЖДЕНИЕ ЗАКАЗА</b>\n\n"
        f"├ 📊 Тариф: 💎 {plan.duration_days} дн. · {devices} устр\n"
        f"├ 📱 Устройств: Стандарт ({devices})\n"
        f"└ 💲 К оплате: {final} ₽ <s>{total_raw} ₽</s>"
    )
    await message.answer(msg, reply_markup=order_confirm_keyboard(plan_id, devices, True, promo.code), parse_mode="HTML")
