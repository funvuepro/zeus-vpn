import logging
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import User
from bot.handlers.start import build_menu_text
from bot.keyboards.inline import about_back_keyboard, about_keyboard, main_menu_keyboard, terms_accept_keyboard
from bot.utils import smart_edit, send_section
from bot.services.remnawave import remnawave

router = Router()

_PRIVACY = (
    "📄 <b>ПОЛИТИКА КОНФИДЕНЦИАЛЬНОСТИ Zeus VPN</b>\n"
    "<i>Редакция от 01.06.2025</i>\n\n"
    "<b>1. Какие данные мы собираем</b>\n"
    "Telegram ID, имя пользователя, данные о подписке, история платежей.\n\n"
    "<b>2. Цели обработки</b>\n"
    "Предоставление услуг, обработка платежей, техническая поддержка, улучшение сервиса.\n\n"
    "<b>3. Хранение данных</b>\n"
    "Данные хранятся на серверах в Российской Федерации в соответствии с требованиями "
    "Федерального закона № 152-ФЗ «О персональных данных». Срок хранения — на протяжении "
    "всего времени использования сервиса и 3 года после удаления аккаунта.\n\n"
    "<b>4. Передача третьим лицам</b>\n"
    "Платёжные данные обрабатываются платёжным оператором (ЮKassa) в рамках "
    "их собственных политик конфиденциальности. Иным третьим лицам данные не передаются, "
    "за исключением случаев, предусмотренных законодательством РФ.\n\n"
    "<b>5. Ваши права</b>\n"
    "Вы вправе запросить доступ, исправление или удаление своих данных, обратившись "
    "в поддержку: @zeus_vpnsupport\n\n"
    "<b>6. Изменения политики</b>\n"
    "Актуальная версия всегда доступна в разделе «О сервисе» бота."
)

_TERMS = (
    "📋 <b>ПОЛЬЗОВАТЕЛЬСКОЕ СОГЛАШЕНИЕ Zeus VPN</b>\n"
    "<i>Редакция от 01.06.2025. Публичная оферта в соответствии со ст. 437 ГК РФ.</i>\n\n"
    "<b>1. Предмет соглашения</b>\n"
    "Zeus VPN предоставляет услуги по организации сетевого соединения через "
    "удалённые серверы (далее — Услуга) для физических лиц на условиях "
    "настоящего Соглашения.\n\n"
    "<b>2. Принятие условий</b>\n"
    "Нажатие кнопки «Принимаю условия» является полным и безоговорочным акцептом "
    "настоящей оферты в соответствии со ст. 438 ГК РФ.\n\n"
    "<b>3. Разрешённое использование</b>\n"
    "Услуга предназначена для: повышения стабильности и скорости интернет-соединения, "
    "удалённого доступа к корпоративным ресурсам, подключения нескольких устройств "
    "к единой сети.\n\n"
    "<b>4. Запрещённое использование</b>\n"
    "Пользователю строго запрещено:\n"
    "— использовать Услугу для доступа к ресурсам, запрещённым законодательством РФ;\n"
    "— осуществлять любую незаконную деятельность с использованием Услуги;\n"
    "— нарушать права и законные интересы третьих лиц;\n"
    "— передавать реквизиты доступа третьим лицам.\n\n"
    "<b>5. Оплата и возврат</b>\n"
    "Услуга предоставляется на условиях предоплаты. Поскольку Услуга является "
    "цифровой и предоставляется немедленно после оплаты, возврат денежных средств "
    "после активации подписки не производится (п. 4 ст. 26.1 Закона о защите прав "
    "потребителей, Постановление Правительства РФ № 612 от 27.09.2007).\n\n"
    "<b>6. Ответственность сторон</b>\n"
    "Пользователь несёт полную ответственность за законность своих действий при "
    "использовании Услуги. Сервис не несёт ответственности за действия Пользователей, "
    "противоречащие настоящему Соглашению или законодательству РФ.\n\n"
    "<b>7. Расторжение</b>\n"
    "При нарушении условий Соглашения доступ к Услуге может быть прекращён "
    "без возврата средств.\n\n"
    "По вопросам: @zeus_vpnsupport"
)

_TERMS_ACCEPT_TEXT = (
    "⚠️ <b>Прежде чем начать</b>\n\n"
    "Zeus VPN предоставляет услуги по организации сетевого соединения через "
    "удалённые серверы.\n\n"
    "Сервис предназначён исключительно для:\n"
    "• Повышения стабильности и скорости интернет-соединения\n"
    "• Удалённого доступа к корпоративным ресурсам\n"
    "• Подключения нескольких устройств к единой сети\n\n"
    "❌ <b>Строго запрещено</b> использование сервиса для доступа к ресурсам, "
    "запрещённым законодательством РФ, а также для любой иной незаконной деятельности.\n\n"
    "Нажимая «Принимаю условия», вы подтверждаете согласие с Пользовательским "
    "соглашением и Политикой конфиденциальности Zeus VPN."
)


@router.callback_query(F.data == "accept_terms")
async def accept_terms_handler(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
    if not user:
        return

    user.terms_accepted = True
    user.terms_accepted_at = datetime.now(timezone.utc)

    if not user.remnawave_uuid:
        try:
            _, remnawave_uuid = await remnawave.create_user(f"user_{user.telegram_id}", expire_days=3)
            user.remnawave_uuid = remnawave_uuid
        except Exception as e:
            logging.warning(f"Remnawave provisioning failed for user {user.telegram_id}: {e}")

    await session.commit()
    await session.refresh(user)

    await send_section(callback, "main", build_menu_text(user), main_menu_keyboard(has_access=user.access_active))


@router.callback_query(F.data == "about")
async def about_handler(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))

    if not user or not user.terms_accepted:
        await smart_edit(callback, _TERMS_ACCEPT_TEXT, terms_accept_keyboard())
        return

    await smart_edit(
        callback,
        "ℹ️ <b>О СЕРВИСЕ Zeus VPN</b>\n\n"
        "Zeus VPN — сервис организации стабильного сетевого соединения через "
        "удалённые серверы для частных пользователей.\n\n"
        "📧 Поддержка: @zeus_vpnsupport\n\n"
        "Выберите раздел:",
        about_keyboard(),
    )


@router.callback_query(F.data == "about_privacy")
async def about_privacy_handler(callback: CallbackQuery):
    await callback.answer()
    await smart_edit(callback, _PRIVACY, about_back_keyboard())


@router.callback_query(F.data == "about_terms")
async def about_terms_handler(callback: CallbackQuery):
    await callback.answer()
    await smart_edit(callback, _TERMS, about_back_keyboard())


@router.callback_query(F.data == "about_support")
async def about_support_handler(callback: CallbackQuery):
    await callback.answer()
    await smart_edit(
        callback,
        "🆘 <b>Поддержка Zeus VPN</b>\n\n"
        "По всем вопросам обращайтесь:\n\n"
        "✍️ Telegram: @zeus_vpnsupport\n\n"
        "Время ответа: как правило, в течение нескольких часов.",
        about_back_keyboard(),
    )


def get_terms_accept_text() -> str:
    return _TERMS_ACCEPT_TEXT
