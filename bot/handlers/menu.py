from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import User
from bot.handlers.start import build_menu_text
from bot.keyboards.inline import (
    back_to_menu_keyboard,
    connect_vpn_keyboard,
    main_menu_keyboard,
    support_keyboard,
)
from bot.services.remnawave import remnawave
from bot.utils import send_section, smart_edit

router = Router()


@router.callback_query(F.data == "connect_vpn")
async def connect_vpn_handler(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))

    if user and user.access_active:
        from bot.handlers.devices import _ensure_remnawave_uuid

        sub_url = ""
        try:
            await _ensure_remnawave_uuid(user, session)
            sub_url = await remnawave.get_subscription_url(f"user_{user.telegram_id}")
        except Exception:
            pass

        if sub_url:
            text = (
                "⚡️ <b>ПОДКЛЮЧИТЬ VPN</b>\n\n"
                f"💰 Баланс: <b>{user.balance} ₽</b>\n"
                f"📱 Устройств: <b>{user.devices_limit}</b>\n\n"
                "📋 <b>Ссылка подписки:</b>\n"
                f"<code>{sub_url}</code>\n\n"
                "Скопируй ссылку и вставь в:\n"
                "• <b>Hiddify</b> (рекомендуем)\n"
                "• <b>v2rayNG</b> / <b>Happ</b>"
            )
        else:
            text = (
                "⚡️ <b>ПОДКЛЮЧИТЬ VPN</b>\n\n"
                f"💰 Баланс: <b>{user.balance} ₽</b>\n\n"
                "⚠️ Не удалось загрузить ссылку подписки.\n"
                "Попробуй позже или обратись в поддержку."
            )
    else:
        text = (
            "⚡️ <b>ПОДКЛЮЧИТЬ VPN</b>\n\n"
            "❌ Доступ отключён — баланс исчерпан.\n\n"
            "Пополни баланс, чтобы получить доступ к Zeus VPN."
        )

    await smart_edit(callback, text, connect_vpn_keyboard(has_access=bool(user and user.access_active)))


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))

    if not user or not user.terms_accepted:
        from bot.handlers.about import get_terms_accept_text
        from bot.keyboards.inline import terms_accept_keyboard
        await smart_edit(callback, get_terms_accept_text(), terms_accept_keyboard())
        return

    await send_section(
        callback,
        "main",
        build_menu_text(user),
        main_menu_keyboard(has_access=user.access_active),
    )


@router.callback_query(F.data == "support")
async def support(callback: CallbackQuery):
    await callback.answer()
    await send_section(
        callback,
        "support",
        "🆘 <b>Поддержка Zeus VPN</b>\n\n"
        "Возникли вопросы или проблемы с подключением?\n"
        "Напиши нам — поможем разобраться.\n\n"
        "⏱ Время ответа: до 24 часов.",
        support_keyboard(),
    )
