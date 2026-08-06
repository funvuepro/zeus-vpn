from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import User
from bot.keyboards.inline import referral_keyboard, back_to_menu_keyboard
from bot.services.referral import get_referral_registered_count, get_referral_paid_count
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

    earned_days = paid * 5
    await smart_edit(
        callback,
        f"🎁 <b>РЕФЕРАЛЬНАЯ ПРОГРАММА DS-VPN</b>\n\n"
        f"Приглашайте друзей и получайте бонусные дни подписки!\n\n"
        f"🔗 <b>ВАША ССЫЛКА:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"📊 <b>СТАТИСТИКА:</b>\n"
        f"┣ 👥 Переходов: <b>0</b>\n"
        f"┣ ✅ Регистраций: <b>{registered}</b>\n"
        f"┣ 💳 Оплатили: <b>{paid}</b>\n"
        f"┗ 🎁 Заработано дней: <b>{earned_days} дн.</b>\n\n"
        f"💡 <b>КАК ЭТО РАБОТАЕТ:</b>\n"
        f"1️⃣ Отправьте вашу ссылку другу\n"
        f"2️⃣ Друг регистрируется и покупает подписку\n"
        f"3️⃣ Вам начисляется <b>+5 бонусных дней</b>\n"
        f"4️⃣ Другу начисляется <b>+10 бонусных дней</b>\n\n"
        f"<i>За пробный период дни не начисляются</i>",
        referral_keyboard(ref_link),
    )