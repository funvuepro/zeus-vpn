import asyncio
import logging

from aiogram import Bot, Dispatcher
from sqlalchemy import select
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_settings
from bot.database.session import AsyncSessionLocal
from bot.handlers import about, admin, devices, fallback, instruction, menu, payment, promo, referral, start

logging.basicConfig(level=logging.INFO)

_bot_instance = None


async def session_middleware(handler, event, data):
    async with AsyncSessionLocal() as session:
        data["session"] = session
        try:
            return await handler(event, data)
        except Exception:
            await session.rollback()
            raise


async def ban_middleware(handler, event, data):
    from aiogram.types import Message, CallbackQuery
    from sqlalchemy import select
    from bot.database.models import User

    tg_id = None
    if isinstance(event, Message):
        tg_id = event.from_user.id if event.from_user else None
    elif isinstance(event, CallbackQuery):
        tg_id = event.from_user.id if event.from_user else None

    if tg_id and "session" in data:
        user = await data["session"].scalar(select(User).where(User.telegram_id == tg_id))
        if user and user.is_banned:
            if isinstance(event, Message):
                await event.answer("🚫 Ваш аккаунт заблокирован.")
            elif isinstance(event, CallbackQuery):
                await event.answer("🚫 Ваш аккаунт заблокирован.", show_alert=True)
            return

        # If user exists but hasn't accepted terms, block most actions until acceptance
        if user and not getattr(user, "terms_accepted", False):
            from aiogram.types import Message, CallbackQuery
            if isinstance(event, CallbackQuery):
                # allow only accept_terms callback
                data_payload = event.data or ""
                if data_payload != "accept_terms":
                    await event.answer("Пожалуйста, сначала примите условия использования.", show_alert=True)
                    return
            elif isinstance(event, Message):
                # allow /start command to re-show terms
                if event.text and event.text.startswith("/start"):
                    return await handler(event, data)
                await event.answer("Пожалуйста, сначала примите условия использования. Нажмите \"Принимаю условия\" в сообщении бота.")
                return

    return await handler(event, data)


async def _init_db():
    from bot.database.session import engine
    from bot.database.models import Base, AppSettings
    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from bot.database.session import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        existing = await session.get(AppSettings, 1)
        if existing is None:
            session.add(AppSettings(id=1, daily_rate_per_device=1.00))
            await session.commit()


async def main():
    global _bot_instance
    await _init_db()
    s = get_settings()
    bot = Bot(
        token=s.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    _bot_instance = bot

    from bot.services import balance as balance_service
    from bot.services import referral as referral_service

    async def _notify(telegram_id: int, text: str):
        try:
            await bot.send_message(telegram_id, text, parse_mode="HTML")
        except Exception:
            pass

    balance_service.notify_user = _notify
    referral_service.notify_user = _notify
    dp = Dispatcher()
    dp.update.middleware(session_middleware)
    dp.update.middleware(ban_middleware)

    dp.include_router(about.router)
    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(instruction.router)
    dp.include_router(menu.router)
    dp.include_router(devices.router)
    dp.include_router(payment.router)
    dp.include_router(referral.router)
    dp.include_router(promo.router)
    dp.include_router(fallback.router)  # must be last

    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from bot.scheduler.tasks import run_daily_billing

    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(run_daily_billing, "cron", hour=0, minute=0)
    scheduler.start()

    from aiogram.types import BotCommandScopeDefault, BotCommandScopeChat
    await bot.set_my_commands(
        [BotCommand(command="start", description="Главное меню Zeus VPN")],
        scope=BotCommandScopeDefault(),
    )
    # Show /admin only to admins
    from bot.database.session import AsyncSessionLocal
    from bot.database.models import User as _User
    async with AsyncSessionLocal() as _s:
        admins = (await _s.execute(select(_User).where(_User.is_admin == True))).scalars().all()
    for _admin in admins:
        try:
            await bot.set_my_commands(
                [
                    BotCommand(command="start", description="Главное меню Zeus VPN"),
                    BotCommand(command="admin", description="Панель администратора"),
                ],
                scope=BotCommandScopeChat(chat_id=_admin.telegram_id),
            )
        except Exception:
            pass
    import uvicorn
    from bot.webhooks.app import create_app

    webhook_app = create_app()
    uvicorn_kwargs = dict(host="0.0.0.0", port=8443, log_level="info")
    if s.SSL_CERT_PATH and s.SSL_KEY_PATH:
        uvicorn_kwargs["ssl_certfile"] = s.SSL_CERT_PATH
        uvicorn_kwargs["ssl_keyfile"] = s.SSL_KEY_PATH
    config = uvicorn.Config(webhook_app, **uvicorn_kwargs)
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None

    await asyncio.gather(
        dp.start_polling(bot),
        server.serve(),
    )


if __name__ == "__main__":
    asyncio.run(main())
