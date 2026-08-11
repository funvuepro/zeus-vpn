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
    back_to_menu_keyboard,
    devices_count_keyboard,
    main_menu_keyboard,
    payment_formed_keyboard,
    topup_amount_prompt_keyboard,
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


@router.callback_query(F.data == "topup")
async def topup_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    s = get_settings()
    if not s.YOOKASSA_SHOP_ID or not s.YOOKASSA_SECRET_KEY:
        await smart_edit(callback, PROVIDER_UNAVAILABLE_MESSAGE, back_to_menu_keyboard())
        return
    await state.set_state(PaymentStates.waiting_for_amount)
    await smart_edit(
        callback,
        f"💰 <b>ПОПОЛНЕНИЕ БАЛАНСА</b>\n\nВведите сумму (минимум {s.MIN_TOPUP_RUB:.0f} ₽):",
        topup_amount_prompt_keyboard(),
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

    payment = Payment(user_id=user.id, provider=PaymentProvider.yookassa, amount=Decimal(str(amount)))
    session.add(payment)
    await session.flush()
    await session.commit()

    pay_url = await create_payment(amount, payment.id, "Пополнение баланса Zeus VPN")

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
    new_limit = int(callback.data.split(":")[1])
    user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
    user.devices_limit = new_limit
    await session.commit()
    await smart_edit(
        callback,
        f"✅ Число устройств обновлено: <b>{new_limit}</b>",
        main_menu_keyboard(has_access=user.access_active),
    )
