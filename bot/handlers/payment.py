from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_settings
from bot.database.models import Payment, PaymentProvider, User
from bot.keyboards.inline import (
    DEVICE_OPTIONS,
    back_to_menu_keyboard,
    devices_count_keyboard,
    payment_formed_keyboard,
    topup_amount_prompt_keyboard,
    topup_menu_keyboard,
)
from bot.services.yookassa import create_payment
from bot.utils import smart_edit

router = Router()

MIN_TOPUP_MESSAGE = "⚡ Минимальная сумма пополнения — {min_amount:.0f} ₽"
PROVIDER_UNAVAILABLE_MESSAGE = "⚡ Пополнение баланса скоро откроется"


class PaymentStates(StatesGroup):
    waiting_for_amount = State()


def _validate_topup_amount(amount: float, min_amount: float) -> tuple[bool, str | None]:
    if amount < min_amount:
        return False, MIN_TOPUP_MESSAGE.format(min_amount=min_amount)
    return True, None


async def _start_payment(user: User, amount: float, session: AsyncSession) -> tuple[str | None, str | None]:
    """Create a pending Payment row and a YooKassa confirmation link.

    Returns (pay_url, error). On failure (missing credentials, YooKassa
    down) rolls back the pending row so it doesn't linger unpaid forever.
    """
    payment = Payment(user_id=user.id, provider=PaymentProvider.yookassa, amount=Decimal(str(amount)))
    session.add(payment)
    await session.flush()
    await session.commit()

    try:
        pay_url = await create_payment(amount, payment.id, "Пополнение баланса Zeus VPN")
    except Exception:
        await session.delete(payment)
        await session.commit()
        return None, PROVIDER_UNAVAILABLE_MESSAGE

    return pay_url, None


@router.callback_query(F.data == "topup")
async def topup_start(callback: CallbackQuery):
    await callback.answer()
    s = get_settings()
    await smart_edit(
        callback,
        f"💰 <b>ПОПОЛНЕНИЕ БАЛАНСА</b>\n\nВыберите сумму или введите свою (минимум {s.MIN_TOPUP_RUB:.0f} ₽):",
        topup_menu_keyboard(),
    )


@router.callback_query(F.data == "topup_custom")
async def topup_custom_prompt(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    s = get_settings()
    await state.set_state(PaymentStates.waiting_for_amount)
    await smart_edit(
        callback,
        f"💰 <b>ПОПОЛНЕНИЕ БАЛАНСА</b>\n\nВведите сумму (минимум {s.MIN_TOPUP_RUB:.0f} ₽):",
        topup_amount_prompt_keyboard(),
    )


@router.callback_query(F.data.startswith("topup_amount:"))
async def topup_preset(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    s = get_settings()
    try:
        amount = float(callback.data.split(":")[1])
    except (IndexError, ValueError):
        return

    ok, error = _validate_topup_amount(amount, s.MIN_TOPUP_RUB)
    if not ok:
        await smart_edit(callback, error, topup_menu_keyboard())
        return

    user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
    pay_url, error = await _start_payment(user, amount, session)
    if error:
        await smart_edit(callback, error, back_to_menu_keyboard())
        return

    await smart_edit(
        callback,
        f"💰 <b>ПЛАТЁЖ СФОРМИРОВАН</b>\n\n└ 💲 Сумма: {amount:.0f} ₽\n\nНажмите кнопку ниже для оплаты.",
        payment_formed_keyboard(pay_url),
    )


@router.message(PaymentStates.waiting_for_amount)
async def topup_amount_input(message: Message, session: AsyncSession, state: FSMContext):
    await state.clear()
    s = get_settings()

    try:
        amount = float(message.text.strip().replace(",", "."))
    except ValueError:
        await message.answer("❌ Введите число, например: 200", reply_markup=back_to_menu_keyboard())
        return

    ok, error = _validate_topup_amount(amount, s.MIN_TOPUP_RUB)
    if not ok:
        await message.answer(error, reply_markup=back_to_menu_keyboard())
        return

    user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
    pay_url, error = await _start_payment(user, amount, session)
    if error:
        await message.answer(error, reply_markup=back_to_menu_keyboard())
        return

    await message.answer(
        f"💰 <b>ПЛАТЁЖ СФОРМИРОВАН</b>\n\n└ 💲 Сумма: {amount:.0f} ₽\n\nНажмите кнопку ниже для оплаты.",
        reply_markup=payment_formed_keyboard(pay_url),
    )


@router.callback_query(F.data == "change_devices")
async def change_devices_start(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
    await smart_edit(
        callback,
        f"🔢 <b>ЧИСЛО УСТРОЙСТВ</b>\n\nСейчас: {user.devices_limit}. Выберите новое значение — влияет на суточное списание:",
        devices_count_keyboard(user.devices_limit),
    )


@router.callback_query(F.data.startswith("set_devices:"))
async def set_devices(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    # callback_data is attacker-controlled (any MTProto client can craft it):
    # devices_limit == -1 would make the daily charge exactly 0.00 (free service),
    # devices_limit == 0 would halve it. Only offered values are accepted.
    try:
        new_limit = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        return
    if new_limit not in DEVICE_OPTIONS:
        return
    user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
    if not user:
        return
    user.devices_limit = new_limit
    await session.commit()

    from bot.handlers.devices import my_devices
    await my_devices(callback, session)
