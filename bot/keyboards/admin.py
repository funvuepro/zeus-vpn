from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def admin_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="adm_users:0")],
        [InlineKeyboardButton(text="⚡ Ставка/день", callback_data="adm_set_rate")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="adm_stats")],
        [InlineKeyboardButton(text="🏷 Промокоды", callback_data="adm_promos")],
        [InlineKeyboardButton(text="🖥 Серверы", callback_data="adm_servers")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="adm_broadcast")],
        [InlineKeyboardButton(text="📖 Инструкции", callback_data="adm_instructions")],
        [InlineKeyboardButton(text="📶 Тексты Подключить", callback_data="adm_connect_texts")],
        [InlineKeyboardButton(text="🖼 Фото разделов", callback_data="adm_photos")],
        [InlineKeyboardButton(text="✖️ Закрыть", callback_data="adm_close")],
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
        )])
    buttons.append([InlineKeyboardButton(text="◀️ Меню", callback_data="adm_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_users_keyboard(users: list, page: int, total: int, page_size: int = 10) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"#{u.telegram_id} @{u.username or '—'}", callback_data=f"adm_user:{u.id}")]
        for u in users
    ]
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"adm_users:{page - 1}"))
    if (page + 1) * page_size < total:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"adm_users:{page + 1}"))
    if nav:
        buttons.append(nav)
    buttons.append([
        InlineKeyboardButton(text="🔍 Поиск по ID", callback_data="adm_search_user"),
        InlineKeyboardButton(text="◀️ Меню", callback_data="adm_menu"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_user_keyboard(user_id: int, is_banned: bool) -> InlineKeyboardMarkup:
    ban_btn = (
        InlineKeyboardButton(text="✅ Разбанить", callback_data=f"adm_unban:{user_id}")
        if is_banned
        else InlineKeyboardButton(text="🚫 Забанить", callback_data=f"adm_ban:{user_id}")
    )
    return InlineKeyboardMarkup(inline_keyboard=[
        [ban_btn],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm_users:0")],
    ])


def admin_promos_keyboard(promos: list) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"🗑 {p.code} ({p.amount} ₽)", callback_data=f"adm_del_promo:{p.id}")]
        for p in promos
    ]
    buttons.append([InlineKeyboardButton(text="➕ Создать промокод", callback_data="adm_new_promo")])
    buttons.append([InlineKeyboardButton(text="◀️ Меню", callback_data="adm_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_back_keyboard(target: str = "adm_menu") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Меню", callback_data=target)]
    ])


def admin_instructions_keyboard(prefix: str = "adm_instr_edit", back: str = "adm_instructions") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 Android", callback_data=f"{prefix}:android")],
        [InlineKeyboardButton(text="🍎 iOS", callback_data=f"{prefix}:ios")],
        [InlineKeyboardButton(text="🖥 Windows", callback_data=f"{prefix}:windows")],
        [InlineKeyboardButton(text="🍏 macOS", callback_data=f"{prefix}:macos")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=back)],
    ])


def admin_servers_keyboard(servers: list) -> InlineKeyboardMarkup:
    buttons = []
    for s in servers:
        status = "✅" if s.is_active else "⛔️"
        backup = " [резерв]" if s.is_backup else ""
        buttons.append([
            InlineKeyboardButton(
                text=f"{status} {s.name} — {s.ip}:{s.port}{backup}",
                callback_data=f"adm_srv_toggle:{s.id}",
            ),
            InlineKeyboardButton(text="🗑", callback_data=f"adm_srv_del:{s.id}"),
        ])
    buttons.append([InlineKeyboardButton(text="➕ Добавить сервер", callback_data="adm_srv_add")])
    buttons.append([InlineKeyboardButton(text="◀️ Меню", callback_data="adm_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Отправить", callback_data="adm_broadcast_send")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="adm_menu")],
    ])
