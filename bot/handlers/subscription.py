from datetime import datetime, timezone, timedelta

from sqlalchemy import text
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Plan, Subscription, SubscriptionStatus, User
from bot.keyboards.inline import devices_select_keyboard, plans_keyboard
from bot.utils import send_section, smart_edit

router = Router()

MSK = timezone(timedelta(hours=3))


def _sub_header(sub: Subscription | None) -> str:
    if not sub:
        return ""
    expires_msk = sub.expires_at.replace(tzinfo=timezone.utc).astimezone(MSK)
    days_left = (sub.expires_at.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)).days
    return (
        "<b>📋 ВАША ПОДПИСКА:</b>\n"
        f"┣ ✅ Статус: Активна\n"
        f"┣ 📅 До: {expires_msk.strftime('%d.%m.%Y')}\n"
        f"┗ ⏳ Осталось: {days_left} дней\n\n"
    )


@router.callback_query(F.data == "buy_subscription")
async def show_plans(callback: CallbackQuery, session: AsyncSession):
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

    result = await session.execute(
        select(Plan)
        .where(Plan.duration_days > 0)
        .where(text("(plans.is_active = 1 OR plans.is_active = 'true')"))
        .order_by(Plan.duration_days)
    )
    plans = result.scalars().all()

    devices_str = f"{sub.devices_limit} устр. (можно добавить ещё)" if sub else "1 устройство (можно добавить ещё)"

    msg = (
        "🗂 <b>ВЫБЕРИТЕ ТАРИФ</b>\n\n"
        + _sub_header(sub) +
        "<b>⚡️ DS-VPN — всё включено:</b>\n"
        "┣ ⚡ Скорость до 1000 Мбит/с\n"
        "┣ 🔵 Трафик: без ограничений\n"
        f"┣ 📱 {devices_str}\n"
        "┗ 🌐 Стабильное соединение 24/7"
    )

    await send_section(callback, "plans", msg, plans_keyboard(plans))


@router.callback_query(F.data.startswith("plan:"))
async def select_plan(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    await callback.answer()
    plan_id = int(callback.data.split(":")[1])
    plan = await session.get(Plan, plan_id)
    await state.clear()
    await state.update_data(plan_id=plan_id)
    msg = (
        f"❓ <b>СКОЛЬКО УСТРОЙСТВ?</b>\n\n"
        f"├ ⏳ 💎 Длительность: {plan.duration_days} дней\n"
        f"└ Выберите тариф ниже:"
    )
    await smart_edit(callback, msg, devices_select_keyboard(plan_id, plan.duration_days))
