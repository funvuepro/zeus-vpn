import os
from datetime import datetime, timezone, timedelta

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message, FSInputFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Subscription, SubscriptionStatus, User
from bot.keyboards.inline import main_menu_keyboard, terms_accept_keyboard
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


def build_menu_text(user: User, sub: Subscription | None) -> str:
    if sub:
        expires_msk = sub.expires_at.replace(tzinfo=timezone.utc).astimezone(MSK)
        day = expires_msk.day
        month = _RU_MONTHS[expires_msk.month - 1]
        time_str = expires_msk.strftime("%H:%M")
        now = datetime.now(timezone.utc)
        days_left = max(0, (sub.expires_at.replace(tzinfo=timezone.utc) - now).days)
        sub_lines = (
            f"✅ Подписка: <b>Активна</b>\n"
            f"📆 Истекает: {day} {month} в {time_str}\n"
            f"       <i>через {days_left} {_days_word(days_left)}</i>\n"
            f"📱 Устройств: {sub.devices_limit}"
        )
    else:
        sub_lines = "❌ Подписка: <b>Не активна</b>"

    return (
        f"⚡️ <b>ПОДПИСКА DS-VPN</b>\n\n"
        f"🆔 ID: <code>{user.telegram_id}</code>\n\n"
        f"{sub_lines}\n\n"
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
        )
        session.add(user)
        await session.commit()
    elif referred_by_id and referred_by_id != user.referred_by:
        # Already registered user tried to use a referral link
        await message.answer(
            "❌ <b>Бонус не получен</b>\n\n"
            "Вы уже зарегистрированы в DS-VPN.\n"
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

    result = await session.execute(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.status == SubscriptionStatus.active,
        ).order_by(Subscription.expires_at.desc())
    )
    sub = result.scalar_one_or_none()

    text = build_menu_text(user, sub)
    keyboard = main_menu_keyboard(has_sub=bool(sub))

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

