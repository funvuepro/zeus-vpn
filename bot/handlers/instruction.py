from aiogram import Router, F
from aiogram.enums import ButtonStyle
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from bot.utils import smart_edit

router = Router()


_INSTRUCTION_TEXT = (
    "📖 <b>Как пользоваться Zeus VPN</b>\n\n"
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
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu", style=ButtonStyle.PRIMARY)],
        ]),
    )
