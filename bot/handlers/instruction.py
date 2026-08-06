from aiogram import Router, F
from aiogram.enums import ButtonStyle
from aiogram.types import CallbackQuery, CopyTextButton, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Subscription, SubscriptionStatus, User
from bot.services.remnawave import remnawave
from bot.utils import smart_edit

router = Router()


def _connect_keyboard(sub_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📲 Открыть подписку", url=sub_url, style=ButtonStyle.SUCCESS)],
        [InlineKeyboardButton(
            text="📋 Скопировать ссылку",
            copy_text=CopyTextButton(text=sub_url),
            style=ButtonStyle.PRIMARY,
        )],
        [InlineKeyboardButton(text="➕ Добавить устройство", callback_data="add_devices")],
        [InlineKeyboardButton(text="💎 Продлить подписку", callback_data="buy_subscription")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")],
    ])


_INSTRUCTION_TEXT = (
    "📖 <b>Как пользоваться DS-VPN</b>\n\n"
    "<b>1️⃣ Купи подписку</b>\n"
    "Нажми «💎 Купить подписку», выбери тариф и оплати удобным способом.\n\n"
    "<b>2️⃣ Подключись</b>\n"
    "Нажми «⚡️ Подключить VPN» → нажми «Открыть подписку» → "
    "скачай Happ → нажми «Добавить подписку».\n\n"
    "<b>3️⃣ Включи VPN</b>\n"
    "Открой Happ и нажми кнопку подключения. Готово — ты защищён.\n\n"
    "➖➖➖➖➖➖➖➖➖\n"
    "📱 Одна подписка — несколько устройств\n"
    "➕ Добавить устройства — в разделе «Мои устройства»\n"
    "🆘 Вопросы — напиши в «Поддержку»"
)


@router.callback_query(F.data == "instruction")
async def show_instruction(callback: CallbackQuery):
    await callback.answer()
    await smart_edit(
        callback,
        _INSTRUCTION_TEXT,
        InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")],
        ]),
    )


@router.callback_query(F.data == "connect_vpn")
async def connect_vpn(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
    if not user:
        return

    sub = await session.scalar(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.status == SubscriptionStatus.active,
        ).order_by(Subscription.expires_at.desc())
    )

    if not sub or not user.remnawave_uuid:
        await smart_edit(
            callback,
            "📶 <b>DS-VPN</b>\n\n"
            "У тебя нет активной подписки.\n\n"
            "Купи DS-VPN и получи доступ к стабильному VPN без ограничений.",
            InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Купить подписку", callback_data="buy_subscription", style=ButtonStyle.SUCCESS)],
                [InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_menu")],
            ]),
        )
        return

    sub_url = await remnawave.get_subscription_url(f"user_{user.telegram_id}")

    await smart_edit(
        callback,
        "📶 <b>Подключить DS-VPN</b>\n\n"
        "1. Нажми «Открыть подписку»\n"
        "2. Скачай приложение Happ для своего устройства\n"
        "3. На странице подписки нажми «Добавить подписку»\n\n"
        f"🔗 Ссылка на твою подписку:\n<code>{sub_url}</code>",
        _connect_keyboard(sub_url),
    )
