from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import User
from bot.keyboards.inline import referral_keyboard
from bot.services.referral import get_referral_registered_count, get_referral_paid_count, REFERRAL_BONUS_RUB
from bot.utils import smart_edit

router = Router()


@router.callback_query(F.data == "referrals")
async def referrals_menu(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    result = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
    user = result.scalar_one()
    registered = await get_referral_registered_count(user.id, session)
    paid = await get_referral_paid_count(user.id, session)
    me = await callback.bot.get_me()
    ref_link = f"https://t.me/{me.username}?start=ref{callback.from_user.id}"

    await smart_edit(
        callback,
        f"🎁 <b>РЕФЕРАЛЬНАЯ ПРОГРАММА ZEUS VPN</b>\n\n"
        f"Приглашайте друзей и получайте бонус на баланс!\n\n"
        f"🔗 <b>ВАША ССЫЛКА:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"📊 <b>СТАТИСТИКА:</b>\n"
        f"┣ ✅ Регистраций: <b>{registered}</b>\n"
        f"┗ 💳 Оплатили: <b>{paid}</b>\n\n"
        f"💡 <b>КАК ЭТО РАБОТАЕТ:</b>\n"
        f"1️⃣ Отправьте вашу ссылку другу\n"
        f"2️⃣ Друг регистрируется и пополняет баланс\n"
        f"3️⃣ Вам начисляется <b>+{REFERRAL_BONUS_RUB:.0f} ₽</b> на баланс\n\n"
        f"<i>Бонус начисляется один раз, за первое пополнение друга</i>",
        referral_keyboard(ref_link),
    )
