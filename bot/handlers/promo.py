from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import User
from bot.services.balance import reactivate_access
from bot.services.promo import validate_promo, record_usage
from bot.services.promo_admin import create_promo, delete_promo, list_promos

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


@router.message(Command("promo"))
async def cmd_promo_prompt(message: Message, state: FSMContext):
    await state.set_state(PromoStates.waiting_for_code)
    await message.answer("🏷 Введи промокод:")


@router.message(PromoStates.waiting_for_code)
async def promo_code_input(message: Message, session: AsyncSession, state: FSMContext):
    await state.clear()
    await redeem_promo_code(message, session)


async def redeem_promo_code(message: Message, session: AsyncSession) -> None:
    user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
    if not user:
        return
    promo, error = await validate_promo(session, message.text.strip(), user.id)

    if error:
        await message.answer(error)
        return

    from decimal import Decimal
    user.balance += Decimal(promo.amount)
    await record_usage(session, promo.id, user.id)
    # Topping up via promo must lift a grace period / disabled state, exactly
    # like a paid top-up does — otherwise daily billing skips the user forever.
    await reactivate_access(user, session)
    await session.commit()

    await message.answer(
        f"✅ Промокод <b>{promo.code}</b> применён! На баланс зачислено <b>{promo.amount} ₽</b>.\n"
        f"Текущий баланс: <b>{user.balance} ₽</b>",
        parse_mode="HTML",
    )
