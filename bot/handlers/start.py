import os
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message, FSInputFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import User
from bot.keyboards.inline import main_menu_keyboard, terms_accept_keyboard
from bot.services.balance import calculate_daily_charge, get_daily_rate_per_device
from bot.utils import get_section_photo

router = Router()

MSK = timezone(timedelta(hours=3))

_LOGO_PATH = "/app/data/logo.jpg"
_logo_file_id: str | None = None

_RU_MONTHS = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]


def _days_word(n: int) -> str:
    if 11 <= n % 100 <= 19:
        return "дней"
    r = n % 10
    if r == 1: return "день"
    if 2 <= r <= 4: return "дня"
    return "дней"


async def build_menu_text(user: User, session: AsyncSession) -> str:
    rate = await get_daily_rate_per_device(session)
    daily_charge = calculate_daily_charge(rate, user.devices_limit)
    tariff = (
        f"🏷 Ваш тариф: <b>{user.devices_limit} устр.</b> — <b>{daily_charge} ₽/день</b>\n"
        f"<i>Больше устройств — выше суточное списание.</i>"
    )

    if user.access_active:
        status_lines = (
            f"✅ Доступ: <b>Активен</b>\n"
            f"💰 Баланс: <b>{user.balance} ₽</b>\n"
            f"📱 Устройств: {user.devices_limit}\n"
            f"{tariff}"
        )
    else:
        status_lines = (
            f"❌ Доступ: <b>Отключён</b> (баланс исчерпан)\n"
            f"💰 Баланс: <b>{user.balance} ₽</b>\n"
            f"{tariff}"
        )

    instruction = (
        "📖 <b>Как подключиться:</b>\n"
        "1️⃣ Пополни баланс\n"
        "2️⃣ Нажми «⚡️ Подключить VPN» → скопируй ссылку → добавь в Hiddify / v2rayNG / Happ\n"
        "3️⃣ Включи VPN в приложении"
    )

    return (
        f"⚡️ <b>Zeus VPN</b>\n\n"
        f"🆔 ID: <code>{user.telegram_id}</code>\n\n"
        f"{status_lines}\n\n"
        f"{instruction}\n\n"
        f"Выберите раздел:"
    )


@router.message(CommandStart())
async def start_handler(message: Message, session: AsyncSession, command):
    global _logo_file_id

    telegram_id = message.from_user.id
    username = message.from_user.username

    referred_by_id: int | None = None
    if command.args and command.args.startswith("ref"):
        try:
            ref_telegram_id = int(command.args[3:])
            result = await session.execute(select(User).where(User.telegram_id == ref_telegram_id))
            referrer = result.scalar_one_or_none()
            if referrer:
                referred_by_id = referrer.id
        except (ValueError, TypeError):
            pass

    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            telegram_id=telegram_id,
            username=username,
            referred_by=referred_by_id,
            balance=Decimal("1.00"),
            devices_limit=1,
        )
        session.add(user)
        await session.commit()
    elif referred_by_id and referred_by_id != user.referred_by:
        await message.answer(
            "❌ <b>Бонус не получен</b>\n\n"
            "Вы уже зарегистрированы в Zeus VPN.\n"
            "Реферальный бонус начисляется только при первой регистрации.",
            parse_mode="HTML",
        )

    if not user.terms_accepted:
        from bot.handlers.about import get_terms_accept_text
        await message.answer(
            get_terms_accept_text(),
            reply_markup=terms_accept_keyboard(),
            parse_mode="HTML",
        )
        return

    text = await build_menu_text(user, session)
    keyboard = main_menu_keyboard(has_access=user.access_active)

    # One message: photo + caption + keyboard
    global _logo_file_id
    section_photo_id = get_section_photo("main") or _logo_file_id
    if section_photo_id:
        try:
            await message.answer_photo(section_photo_id, caption=text, reply_markup=keyboard, parse_mode="HTML")
            return
        except Exception:
            pass
    if os.path.exists(_LOGO_PATH):
        try:
            sent = await message.answer_photo(FSInputFile(_LOGO_PATH), caption=text, reply_markup=keyboard, parse_mode="HTML")
            if sent.photo:
                _logo_file_id = sent.photo[-1].file_id
            return
        except Exception:
            pass
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

