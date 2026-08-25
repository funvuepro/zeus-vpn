from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import User
from bot.services.balance import calculate_daily_charge, get_daily_rate_per_device
from bot.services.remnawave import remnawave
from bot.utils import smart_edit

router = Router()

_PLATFORMS = {"iOS": "📱", "Android": "🤖", "Windows": "🖥", "macOS": "🍎", "Linux": "🐧"}


def _platform_icon(platform: str) -> str:
    return _PLATFORMS.get(platform, "📟")


def _fmt_dt(iso: str) -> str:
    if not iso:
        return "—"
    try:
        from datetime import datetime, timezone, timedelta
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        msk = dt.astimezone(timezone(timedelta(hours=3)))
        return msk.strftime("%-d.%-m.%Y %H:%M")
    except Exception:
        return iso[:16]


async def _ensure_remnawave_uuid(user: User, session: AsyncSession) -> str | None:
    """If remnawave_uuid is missing, look up (or create, if provisioning never
    succeeded — e.g. Remnawave was unreachable at registration time) the
    Remnawave user and persist its id."""
    if user.remnawave_uuid:
        return user.remnawave_uuid
    username = f"user_{user.telegram_id}"
    from bot.handlers.about import REMNAWAVE_EXPIRE_DAYS
    try:
        data = await remnawave.get_user_by_username(username)
        remnawave_id = data.get("id")
    except Exception:
        try:
            _, remnawave_id = await remnawave.create_user(username, expire_days=REMNAWAVE_EXPIRE_DAYS)
        except Exception:
            return None
    if remnawave_id:
        user.remnawave_uuid = str(remnawave_id)
        await session.commit()
        return user.remnawave_uuid
    return None


def _no_sub_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="topup")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")],
    ])


def _parse_device(d) -> tuple[str, str]:
    """Returns (hwid, display_label) regardless of whether d is a dict or plain HWID string."""
    if isinstance(d, dict):
        hwid = d.get("hwid", str(d))
        platform = d.get("platform", "")
        model = d.get("deviceModel") or platform or "Устройство"
        icon = _platform_icon(platform)
        return hwid, f"{icon} {model}"
    # plain HWID string
    return str(d), f"📟 Устройство"


def _devices_main_keyboard(devices: list) -> InlineKeyboardMarkup:
    buttons = []
    for i, d in enumerate(devices, 1):
        hwid, label = _parse_device(d)
        buttons.append([InlineKeyboardButton(
            text=f"{i}. {label}",
            callback_data=f"device:{hwid}",
        )])
    buttons.append([InlineKeyboardButton(text="➕ Добавить устройство", callback_data="add_devices")])
    buttons.append([InlineKeyboardButton(text="🔢 Изменить лимит устройств", callback_data="change_devices")])
    buttons.append([InlineKeyboardButton(text="🔄 Обновить", callback_data="my_devices")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _device_detail_keyboard(hwid: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚫 Отвязать устройство", callback_data=f"unbind:{hwid}")],
        [InlineKeyboardButton(text="◀️ К списку", callback_data="my_devices")],
    ])


@router.callback_query(F.data == "my_devices")
async def my_devices(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()

    user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
    if not user:
        await smart_edit(callback, "❌ Пользователь не найден.", _no_sub_keyboard())
        return

    if not user.access_active:
        await smart_edit(
            callback,
            "📱 <b>МОИ УСТРОЙСТВА</b>\n\n"
            "❌ Доступ отключён — баланс исчерпан.\n"
            "Пополните баланс, чтобы получить доступ к VPN.",
            _no_sub_keyboard(),
        )
        return

    # Auto-link remnawave_uuid if missing
    uuid = await _ensure_remnawave_uuid(user, session)
    if not uuid:
        await smart_edit(
            callback,
            "📱 <b>МОИ УСТРОЙСТВА</b>\n\n"
            "⚠️ Не удалось получить данные VPN-аккаунта.\n"
            "Обратитесь в поддержку.",
            InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🆘 Поддержка", callback_data="support")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")],
            ]),
        )
        return

    # Fetch devices list
    try:
        resp = await remnawave._request("GET", f"/hwid/devices/{uuid}")
        body = resp.json().get("response", {})
        devices = body.get("devices", []) if isinstance(body, dict) else body
    except Exception:
        devices = []

    count = len(devices)
    limit = user.devices_limit
    rate = await get_daily_rate_per_device(session)
    daily_charge = calculate_daily_charge(rate, limit)
    charge_info = (
        f"💳 Лимит <b>{limit}</b> устр. → списание <b>{daily_charge} ₽/день</b>\n"
        f"<i>Чем больше лимит — тем выше суточное списание.</i>"
    )

    if not devices:
        # No devices yet — show subscription link to get started
        try:
            rn_user = await remnawave.get_user_by_username(f"user_{user.telegram_id}")
            sub_url = rn_user.get("subscriptionUrl", "")
        except Exception:
            sub_url = ""

        text = (
            f"📱 <b>МОИ УСТРОЙСТВА</b>\n"
            f"{'─' * 22}\n"
            f"Подключено: <b>0</b> из <b>{limit}</b>\n"
            f"{charge_info}\n\n"
            f"📡 Устройства ещё не подключены.\n\n"
            f"Чтобы подключиться — скопируй ссылку подписки\n"
            f"из раздела <b>⚡️ Подключить VPN</b> и добавь в\n"
            f"Hiddify, v2rayNG или другой клиент."
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚡️ Подключить VPN", callback_data="connect_vpn")],
            [InlineKeyboardButton(text="➕ Добавить устройство", callback_data="add_devices")],
            [InlineKeyboardButton(text="🔢 Изменить лимит устройств", callback_data="change_devices")],
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="my_devices")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")],
        ])
        await smart_edit(callback, text, keyboard)
        return

    text = (
        f"📱 <b>МОИ УСТРОЙСТВА</b>\n"
        f"{'─' * 22}\n"
        f"Подключено: <b>{count}</b> из <b>{limit}</b>\n"
        f"{charge_info}\n\n"
        f"<i>Нажмите на устройство для подробностей\n"
        f"или чтобы отвязать его.</i>"
    )
    await smart_edit(callback, text, _devices_main_keyboard(devices))


@router.callback_query(F.data.startswith("device:"))
async def device_detail(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    hwid = callback.data.split(":", 1)[1]

    user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
    uuid = await _ensure_remnawave_uuid(user, session) if user else None
    if not uuid:
        await callback.answer("Пользователь не найден", show_alert=True)
        return

    try:
        resp = await remnawave._request("GET", f"/hwid/devices/{uuid}")
        body = resp.json().get("response", {})
        devices = body.get("devices", []) if isinstance(body, dict) else body
    except Exception:
        devices = []

    total = len(devices)
    idx = next(
        (i + 1 for i, d in enumerate(devices) if (_parse_device(d)[0] == hwid)),
        "?"
    )
    matched = next((d for d in devices if _parse_device(d)[0] == hwid), None)

    if matched is None:
        await callback.answer("Устройство не найдено", show_alert=True)
        return

    if isinstance(matched, dict):
        icon = _platform_icon(matched.get("platform", ""))
        model = matched.get("deviceModel") or "—"
        platform = matched.get("platform") or "—"
        os_ver = matched.get("osVersion") or "—"
        added = _fmt_dt(matched.get("createdAt", ""))
        updated = _fmt_dt(matched.get("updatedAt", ""))
        text = (
            f"{icon} <b>УСТРОЙСТВО {idx} из {total}</b>\n"
            f"{'─' * 22}\n"
            f"📱 Модель: <b>{model}</b>\n"
            f"🔧 Платформа: <b>{platform}</b>\n"
            f"💻 ОС: <b>{os_ver}</b>\n"
            f"🆔 HWID: <code>{hwid[:24]}…</code>\n"
            f"➕ Добавлено: <b>{added}</b>\n"
            f"🔄 Активность: <b>{updated}</b>"
        )
    else:
        text = (
            f"📟 <b>УСТРОЙСТВО {idx} из {total}</b>\n"
            f"{'─' * 22}\n"
            f"🆔 HWID: <code>{hwid}</code>\n\n"
            f"<i>Нажмите «Отвязать», чтобы удалить это устройство.</i>"
        )
    await smart_edit(callback, text, _device_detail_keyboard(hwid))


@router.callback_query(F.data.startswith("unbind:"))
async def unbind_device(callback: CallbackQuery, session: AsyncSession):
    hwid = callback.data.split(":", 1)[1]

    user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
    uuid = await _ensure_remnawave_uuid(user, session) if user else None
    if not uuid:
        await callback.answer("Пользователь не найден", show_alert=True)
        return

    try:
        await remnawave._request(
            "POST",
            "/hwid/devices/delete",
            json={"hwid": hwid, "userUuid": uuid},
        )
        await callback.answer("✅ Устройство отвязано", show_alert=True)
    except Exception:
        await callback.answer("❌ Ошибка при отвязке", show_alert=True)
        return

    await my_devices(callback, session)
