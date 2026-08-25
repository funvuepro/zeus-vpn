from aiogram.enums import ButtonStyle
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

S = ButtonStyle.SUCCESS
P = ButtonStyle.PRIMARY
D = ButtonStyle.DANGER


def admin_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="adm_users:0", style=P)],
        [InlineKeyboardButton(text="⚡ Ставка/день", callback_data="adm_set_rate", style=P)],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="adm_stats", style=P)],
        [InlineKeyboardButton(text="🏷 Промокоды", callback_data="adm_promos", style=P)],
        [InlineKeyboardButton(text="🖥 Серверы", callback_data="adm_servers", style=P)],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="adm_broadcast", style=P)],
        [InlineKeyboardButton(text="📖 Инструкции", callback_data="adm_instructions", style=P)],
        [InlineKeyboardButton(text="📶 Тексты Подключить", callback_data="adm_connect_texts", style=P)],
        [InlineKeyboardButton(text="🖼 Фото разделов", callback_data="adm_photos", style=P)],
        [InlineKeyboardButton(text="✖️ Закрыть", callback_data="adm_close", style=D)],
    ])


def admin_photos_keyboard(photos: dict) -> InlineKeyboardMarkup:
    sections = [
        ("🏠 Главная", "main"),
        ("📋 Выбор тарифа", "plans"),
        ("🆘 Поддержка", "support"),
    ]
    buttons = []
    for label, key in sections:
        status = "✅" if photos.get(key) else "❌ не задано"
        buttons.append([InlineKeyboardButton(
            text=f"{status}  {label}",
            callback_data=f"adm_setphoto:{key}",
            style=P,
        )])
    buttons.append([InlineKeyboardButton(text="◀️ Меню", callback_data="adm_menu", style=P)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_users_keyboard(users: list, page: int, total: int, page_size: int = 10) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"#{u.telegram_id} @{u.username or '—'}", callback_data=f"adm_user:{u.id}", style=P)]
        for u in users
    ]
    if page > 0:
        buttons.append([InlineKeyboardButton(text="◀️ Пред. страница", callback_data=f"adm_users:{page - 1}", style=P)])
    if (page + 1) * page_size < total:
        buttons.append([InlineKeyboardButton(text="▶️ След. страница", callback_data=f"adm_users:{page + 1}", style=P)])
    buttons.append([InlineKeyboardButton(text="🔍 Поиск по ID", callback_data="adm_search_user", style=P)])
    buttons.append([InlineKeyboardButton(text="◀️ Меню", callback_data="adm_menu", style=P)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_user_keyboard(user_id: int, is_banned: bool) -> InlineKeyboardMarkup:
    ban_btn = (
        InlineKeyboardButton(text="✅ Разбанить", callback_data=f"adm_unban:{user_id}", style=S)
        if is_banned
        else InlineKeyboardButton(text="🚫 Забанить", callback_data=f"adm_ban:{user_id}", style=D)
    )
    return InlineKeyboardMarkup(inline_keyboard=[
        [ban_btn],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm_users:0", style=P)],
    ])


def admin_promos_keyboard(promos: list) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"🗑 {p.code} ({p.amount} ₽)", callback_data=f"adm_del_promo:{p.id}", style=D)]
        for p in promos
    ]
    buttons.append([InlineKeyboardButton(text="➕ Создать промокод", callback_data="adm_new_promo", style=S)])
    buttons.append([InlineKeyboardButton(text="◀️ Меню", callback_data="adm_menu", style=P)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_back_keyboard(target: str = "adm_menu") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Меню", callback_data=target, style=P)]
    ])


def admin_instructions_keyboard(prefix: str = "adm_instr_edit", back: str = "adm_instructions") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 Android", callback_data=f"{prefix}:android", style=P)],
        [InlineKeyboardButton(text="🍎 iOS", callback_data=f"{prefix}:ios", style=P)],
        [InlineKeyboardButton(text="🖥 Windows", callback_data=f"{prefix}:windows", style=P)],
        [InlineKeyboardButton(text="🍏 macOS", callback_data=f"{prefix}:macos", style=P)],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=back, style=P)],
    ])


def admin_servers_keyboard(servers: list) -> InlineKeyboardMarkup:
    buttons = []
    for s in servers:
        status = "✅" if s.is_active else "⛔️"
        backup = " [резерв]" if s.is_backup else ""
        buttons.append([InlineKeyboardButton(
            text=f"{status} {s.name} — {s.ip}:{s.port}{backup}",
            callback_data=f"adm_srv_toggle:{s.id}",
            style=P,
        )])
        buttons.append([InlineKeyboardButton(text=f"🗑 Удалить {s.name}", callback_data=f"adm_srv_del:{s.id}", style=D)])
    buttons.append([InlineKeyboardButton(text="➕ Добавить сервер", callback_data="adm_srv_add", style=S)])
    buttons.append([InlineKeyboardButton(text="◀️ Меню", callback_data="adm_menu", style=P)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Отправить", callback_data="adm_broadcast_send", style=S)],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="adm_menu", style=D)],
    ])
