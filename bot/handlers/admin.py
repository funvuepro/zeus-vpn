from datetime import datetime, timezone, timedelta

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Payment, PaymentStatus, User, VpnServer
from bot.keyboards.admin import (
    admin_back_keyboard, admin_broadcast_confirm_keyboard, admin_instructions_keyboard,
    admin_main_keyboard, admin_photos_keyboard, admin_promos_keyboard, admin_servers_keyboard,
    admin_user_keyboard, admin_users_keyboard,
)
from bot.services.promo_admin import create_promo, delete_promo, list_promos

router = Router()
PAGE_SIZE = 10

class AdminStates(StatesGroup):
    search_user = State()
    broadcast_text = State()
    new_promo_input = State()
    edit_instruction = State()
    set_rate = State()
    add_server = State()
    set_photo = State()


def _is_admin(user: User) -> bool:
    return user is not None and user.is_admin


async def _get_admin(session: AsyncSession, telegram_id: int) -> User | None:
    user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
    return user if _is_admin(user) else None


# ── Main menu ─────────────────────────────────────────────────────────────────

@router.message(Command("admin"))
async def cmd_admin(message: Message, session: AsyncSession):
    if not await _get_admin(session, message.from_user.id):
        return
    await message.answer("🛠 <b>Панель администратора</b>", reply_markup=admin_main_keyboard())


@router.callback_query(F.data == "adm_close")
async def adm_close(callback: CallbackQuery):
    await callback.answer()
    await callback.message.delete()


@router.callback_query(F.data == "adm_menu")
async def adm_menu(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    if not await _get_admin(session, callback.from_user.id):
        return
    await callback.message.edit_text("🛠 <b>Панель администратора</b>", reply_markup=admin_main_keyboard())


# ── Statistics ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_stats")
async def adm_stats(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    if not await _get_admin(session, callback.from_user.id):
        return

    total_users = await session.scalar(select(func.count(User.id))) or 0
    active_access = await session.scalar(
        select(func.count(User.id)).where(User.access_active == True)
    ) or 0
    total_balance = await session.scalar(select(func.sum(User.balance))) or 0
    total_revenue = await session.scalar(
        select(func.sum(Payment.amount)).where(Payment.status == PaymentStatus.paid)
    ) or 0
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    new_today = await session.scalar(
        select(func.count(User.id)).where(User.created_at >= today)
    ) or 0

    await callback.message.edit_text(
        f"📊 <b>Статистика Zeus VPN</b>\n\n"
        f"👥 Всего пользователей: <b>{total_users}</b>\n"
        f"🆕 Новых сегодня: <b>{new_today}</b>\n"
        f"⚡ С активным доступом: <b>{active_access}</b>\n"
        f"💰 Суммарный баланс пользователей: <b>{round(float(total_balance))} ₽</b>\n"
        f"💳 Общая выручка: <b>{round(float(total_revenue))} ₽</b>",
        reply_markup=admin_back_keyboard(),
    )


# ── Users ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm_users:"))
async def adm_users(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    if not await _get_admin(session, callback.from_user.id):
        return
    page = int(callback.data.split(":")[1])
    total = await session.scalar(select(func.count(User.id))) or 0
    users = (await session.execute(
        select(User).order_by(User.id.desc()).offset(page * PAGE_SIZE).limit(PAGE_SIZE)
    )).scalars().all()
    await callback.message.edit_text(
        f"👥 <b>Пользователи</b> (стр. {page + 1})",
        reply_markup=admin_users_keyboard(users, page, total, PAGE_SIZE),
    )


@router.callback_query(F.data == "adm_search_user")
async def adm_search_user(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AdminStates.search_user)
    await callback.message.edit_text("🔍 Введи ID пользователя:")


@router.message(AdminStates.search_user)
async def adm_search_user_input(message: Message, session: AsyncSession, state: FSMContext):
    await state.clear()
    if not await _get_admin(session, message.from_user.id):
        return
    try:
        telegram_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Неверный формат ID", reply_markup=admin_back_keyboard())
        return
    user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
    if not user:
        await message.answer("❌ Пользователь не найден", reply_markup=admin_back_keyboard())
        return
    await _show_user(message.answer, user, session)


@router.callback_query(F.data.startswith("adm_user:"))
async def adm_user(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    if not await _get_admin(session, callback.from_user.id):
        return
    user_id = int(callback.data.split(":")[1])
    user = await session.get(User, user_id)
    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return
    await _show_user(callback.message.edit_text, user, session)


async def _show_user(send_fn, user: User, session: AsyncSession):
    banned = "🚫 Забанен" if user.is_banned else "✅ Активен"
    access = "✅ Доступ активен" if user.access_active else "❌ Доступ отключён"
    await send_fn(
        f"👤 <b>Пользователь #{user.telegram_id}</b>\n\n"
        f"Telegram ID: <code>{user.telegram_id}</code>\n"
        f"Username: @{user.username or '—'}\n"
        f"Статус: {banned}\n"
        f"{access}\n"
        f"💰 Баланс: {user.balance} ₽\n"
        f"📱 Устройств: {user.devices_limit}",
        reply_markup=admin_user_keyboard(user.id, user.is_banned),
    )


@router.callback_query(F.data.startswith("adm_ban:"))
async def adm_ban(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    if not await _get_admin(session, callback.from_user.id):
        return
    user_id = int(callback.data.split(":")[1])
    user = await session.get(User, user_id)
    user.is_banned = True
    await session.commit()
    await _show_user(callback.message.edit_text, user, session)


@router.callback_query(F.data.startswith("adm_unban:"))
async def adm_unban(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    if not await _get_admin(session, callback.from_user.id):
        return
    user_id = int(callback.data.split(":")[1])
    user = await session.get(User, user_id)
    user.is_banned = False
    await session.commit()
    await _show_user(callback.message.edit_text, user, session)


# ── Daily rate ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_set_rate")
async def adm_set_rate_start(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    await callback.answer()
    if not await _get_admin(session, callback.from_user.id):
        return
    from bot.services.balance import get_daily_rate_per_device
    current = await get_daily_rate_per_device(session)
    await state.set_state(AdminStates.set_rate)
    await callback.message.edit_text(
        f"⚡ Текущая ставка: <b>{current} ₽</b>/устройство/день\n\nВведи новую ставку (например: 1.50):",
    )


@router.message(AdminStates.set_rate)
async def adm_set_rate_input(message: Message, session: AsyncSession, state: FSMContext):
    await state.clear()
    if not await _get_admin(session, message.from_user.id):
        return
    from decimal import Decimal, InvalidOperation
    from bot.services.balance import set_daily_rate_per_device
    try:
        value = Decimal(message.text.strip().replace(",", "."))
        if value <= 0:
            raise InvalidOperation
    except InvalidOperation:
        await message.answer("❌ Введи положительное число, например: 1.50", reply_markup=admin_back_keyboard())
        return
    await set_daily_rate_per_device(session, value)
    await message.answer(f"✅ Ставка обновлена: <b>{value} ₽</b>/устройство/день", reply_markup=admin_back_keyboard())


# ── Promo codes ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_promos")
async def adm_promos(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    if not await _get_admin(session, callback.from_user.id):
        return
    promos, _ = await list_promos(session)
    await callback.message.edit_text(
        "🏷 <b>Промокоды</b>\n\nНажми на код чтобы удалить:",
        reply_markup=admin_promos_keyboard(promos),
    )


@router.callback_query(F.data.startswith("adm_del_promo:"))
async def adm_del_promo(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    if not await _get_admin(session, callback.from_user.id):
        return
    promo_id = int(callback.data.split(":")[1])
    from bot.database.models import PromoCode
    promo = await session.get(PromoCode, promo_id)
    if promo:
        promo.is_active = False
        await session.commit()
    promos, _ = await list_promos(session)
    await callback.message.edit_text(
        "🏷 <b>Промокоды</b>",
        reply_markup=admin_promos_keyboard(promos),
    )


@router.callback_query(F.data == "adm_new_promo")
async def adm_new_promo(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AdminStates.new_promo_input)
    await callback.message.edit_text(
        "🏷 Введи промокод в формате:\n<code>КОД СКИДКА [ДАТА]</code>\n\nПример: <code>SALE50 50 2026-12-31</code>",
    )


@router.message(AdminStates.new_promo_input)
async def adm_new_promo_input(message: Message, session: AsyncSession, state: FSMContext):
    await state.clear()
    if not await _get_admin(session, message.from_user.id):
        return
    parts = message.text.strip().split()
    if len(parts) < 2:
        await message.answer("❌ Неверный формат", reply_markup=admin_back_keyboard())
        return
    code = parts[0].upper()
    try:
        amount = int(parts[1])
    except ValueError:
        await message.answer("❌ Скидка должна быть числом", reply_markup=admin_back_keyboard())
        return
    expires_str = parts[2] if len(parts) > 2 else None
    try:
        promo = await create_promo(session, code, amount, expires_str)
        await session.commit()
        exp = promo.expires_at.strftime("%d.%m.%Y") if promo.expires_at else "бессрочно"
        await message.answer(
            f"✅ Промокод <b>{promo.code}</b> создан\nСкидка: {promo.amount} ₽\nДо: {exp}",
            reply_markup=admin_back_keyboard(),
        )
    except ValueError as e:
        await message.answer(str(e), reply_markup=admin_back_keyboard())


# ── Instructions ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_instructions")
async def adm_instructions(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    if not await _get_admin(session, callback.from_user.id):
        return
    await callback.message.edit_text(
        "📖 <b>Инструкции</b>\n\nВыбери платформу для редактирования:",
        reply_markup=admin_instructions_keyboard(),
    )


@router.callback_query(F.data == "adm_connect_texts")
async def adm_connect_texts(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    if not await _get_admin(session, callback.from_user.id):
        return
    await callback.message.edit_text(
        "📶 <b>Тексты Подключить</b>\n\nВыбери платформу для редактирования:",
        reply_markup=admin_instructions_keyboard(prefix="adm_connect_edit", back="adm_menu"),
    )


async def _edit_instruction(callback, session, state, platform_str, category_str):
    from bot.database.models import Instruction, InstructionCategory, InstructionPlatform
    platform = InstructionPlatform(platform_str)
    category = InstructionCategory(category_str)
    instr = await session.scalar(
        select(Instruction).where(
            Instruction.platform == platform,
            Instruction.category == category,
        )
    )
    current = instr.text if instr else "(пусто)"
    await state.set_state(AdminStates.edit_instruction)
    await state.update_data(platform=platform_str, category=category_str)
    await callback.message.edit_text(
        f"Текущий текст для <b>{platform_str}</b>:\n\n{current}\n\n"
        f"Введи новый текст (HTML поддерживается):",
    )


@router.callback_query(F.data.startswith("adm_instr_edit:"))
async def adm_instr_edit(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    await callback.answer()
    if not await _get_admin(session, callback.from_user.id):
        return
    await _edit_instruction(callback, session, state, callback.data.split(":")[1], "general")


@router.callback_query(F.data.startswith("adm_connect_edit:"))
async def adm_connect_edit(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    await callback.answer()
    if not await _get_admin(session, callback.from_user.id):
        return
    await _edit_instruction(callback, session, state, callback.data.split(":")[1], "connect")


@router.message(AdminStates.edit_instruction)
async def adm_instr_save(message: Message, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    if not await _get_admin(session, message.from_user.id):
        return
    from bot.database.models import Instruction, InstructionCategory, InstructionPlatform
    platform = InstructionPlatform(data["platform"])
    category = InstructionCategory(data.get("category", "general"))
    instr = await session.scalar(
        select(Instruction).where(
            Instruction.platform == platform,
            Instruction.category == category,
        )
    )
    if instr:
        instr.text = message.text
    else:
        session.add(Instruction(platform=platform, category=category, text=message.text))
    await session.commit()
    back = "adm_instructions" if category == InstructionCategory.general else "adm_connect_texts"
    kb = admin_instructions_keyboard() if category == InstructionCategory.general else admin_instructions_keyboard(prefix="adm_connect_edit", back="adm_menu")
    await message.answer(
        f"✅ Текст для <b>{data['platform']}</b> обновлён.",
        reply_markup=kb,
    )


# ── Broadcast ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_broadcast")
async def adm_broadcast(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AdminStates.broadcast_text)
    await callback.message.edit_text("📢 Введи текст рассылки (поддерживается HTML):")


@router.message(AdminStates.broadcast_text)
async def adm_broadcast_text(message: Message, state: FSMContext):
    await state.update_data(broadcast_text=message.html_text)
    await state.set_state(None)
    await message.answer(
        f"📢 <b>Превью рассылки:</b>\n\n{message.html_text}\n\n"
        f"Отправить всем пользователям?",
        reply_markup=admin_broadcast_confirm_keyboard(),
    )


@router.callback_query(F.data == "adm_servers")
async def adm_servers(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    if not await _get_admin(session, callback.from_user.id):
        return
    servers = (await session.execute(
        select(VpnServer).order_by(VpnServer.is_backup, VpnServer.id)
    )).scalars().all()
    text = f"🖥 <b>Серверы DS-VPN</b> ({len(servers)} шт.)\n\n✅ — активен  ⛔️ — отключён  [резерв] — резервный"
    await callback.message.edit_text(text, reply_markup=admin_servers_keyboard(servers), parse_mode="HTML")


@router.callback_query(F.data.startswith("adm_srv_toggle:"))
async def adm_srv_toggle(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    if not await _get_admin(session, callback.from_user.id):
        return
    srv_id = int(callback.data.split(":")[1])
    server = await session.get(VpnServer, srv_id)
    if server:
        server.is_active = not server.is_active
        await session.commit()
    servers = (await session.execute(
        select(VpnServer).order_by(VpnServer.is_backup, VpnServer.id)
    )).scalars().all()
    await callback.message.edit_reply_markup(reply_markup=admin_servers_keyboard(servers))


@router.callback_query(F.data.startswith("adm_srv_del:"))
async def adm_srv_del(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    if not await _get_admin(session, callback.from_user.id):
        return
    srv_id = int(callback.data.split(":")[1])
    server = await session.get(VpnServer, srv_id)
    if server:
        await session.delete(server)
        await session.commit()
    servers = (await session.execute(
        select(VpnServer).order_by(VpnServer.is_backup, VpnServer.id)
    )).scalars().all()
    await callback.message.edit_text(
        f"🖥 <b>Серверы DS-VPN</b> ({len(servers)} шт.)",
        reply_markup=admin_servers_keyboard(servers),
        parse_mode="HTML",
    )


_ADD_SERVER_HELP = """\
➕ <b>Добавить сервер</b>

Отправь данные сервера в формате (каждый параметр на новой строке):

<code>Название
IP-адрес
Порт
Транспорт (tcp или grpc)
PublicKey
ShortId
ServerName (SNI)
Fingerprint (firefox / chrome / qq)
backup (да или нет)</code>

<b>Пример:</b>
<code>Москва-1
89.208.209.184
443
tcp
dDChaMTPomqlPNYMC1x-c4e9nt5XV13eY_tTwdCgPUU
b19883501ce9adae
max.ru
firefox
нет</code>"""


@router.callback_query(F.data == "adm_srv_add")
async def adm_srv_add(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AdminStates.add_server)
    await callback.message.edit_text(_ADD_SERVER_HELP, parse_mode="HTML")


@router.message(AdminStates.add_server)
async def adm_srv_add_input(message: Message, session: AsyncSession, state: FSMContext):
    await state.clear()
    lines = [l.strip() for l in message.text.strip().splitlines() if l.strip()]
    if len(lines) < 8:
        await message.answer("❌ Нужно минимум 8 строк. Попробуй ещё раз через /admin → Серверы.")
        return
    try:
        name, ip, port_str, transport, public_key, short_id, server_name, fingerprint = lines[:8]
        is_backup = len(lines) > 8 and lines[8].lower() in ("да", "yes", "1", "backup")
        server = VpnServer(
            name=name,
            ip=ip,
            port=int(port_str),
            transport=transport.lower(),
            public_key=public_key,
            short_id=short_id,
            server_name=server_name,
            fingerprint=fingerprint.lower(),
            is_backup=is_backup,
            is_active=True,
        )
        session.add(server)
        await session.commit()
        await message.answer(
            f"✅ Сервер <b>{name}</b> ({ip}:{port_str}) добавлен.",
            parse_mode="HTML",
            reply_markup=admin_back_keyboard("adm_servers"),
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка при сохранении: {e}")


@router.callback_query(F.data == "adm_broadcast_send")
async def adm_broadcast_send(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    await callback.answer()
    if not await _get_admin(session, callback.from_user.id):
        return
    data = await state.get_data()
    text = data.get("broadcast_text", "")
    await state.clear()

    users = (await session.execute(
        select(User.telegram_id).where(User.is_banned == False)
    )).scalars().all()

    sent, failed = 0, 0
    for tg_id in users:
        try:
            await callback.bot.send_message(tg_id, text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1

    await callback.message.edit_text(
        f"✅ Рассылка завершена\n\nОтправлено: {sent}\nОшибок: {failed}",
        reply_markup=admin_back_keyboard(),
    )


_PHOTO_SECTIONS = {"main": "Главная", "plans": "Выбор тарифа", "support": "Поддержка"}


@router.callback_query(F.data == "adm_photos")
async def adm_photos(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    if not await _get_admin(session, callback.from_user.id):
        return
    from bot.utils import get_section_photo
    photos = {k: get_section_photo(k) for k in _PHOTO_SECTIONS}
    await callback.message.edit_text(
        "🖼 <b>Фото разделов</b>\n\n"
        "Нажмите на раздел, чтобы загрузить или заменить фото.\n"
        "✅ — фото задано  ❌ — не задано",
        reply_markup=admin_photos_keyboard(photos),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("adm_setphoto:"))
async def adm_setphoto_start(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    await callback.answer()
    if not await _get_admin(session, callback.from_user.id):
        return
    section = callback.data.split(":")[1]
    if section not in _PHOTO_SECTIONS:
        return
    await state.set_state(AdminStates.set_photo)
    await state.update_data(photo_section=section)
    await callback.message.edit_text(
        f"📸 Отправьте фото для раздела <b>{_PHOTO_SECTIONS[section]}</b>:\n\n"
        "Просто пришлите изображение следующим сообщением.",
        reply_markup=admin_back_keyboard("adm_photos"),
        parse_mode="HTML",
    )


@router.message(AdminStates.set_photo, F.photo)
async def receive_section_photo(message: Message, state: FSMContext):
    from bot.utils import set_section_photo, get_section_photo
    data = await state.get_data()
    section = data.get("photo_section", "")
    file_id = message.photo[-1].file_id
    set_section_photo(section, file_id)
    await state.clear()
    label = _PHOTO_SECTIONS.get(section, section)
    photos = {k: get_section_photo(k) for k in _PHOTO_SECTIONS}
    await message.answer(
        f"✅ Фото для раздела <b>{label}</b> сохранено!",
        reply_markup=admin_photos_keyboard(photos),
        parse_mode="HTML",
    )
