from aiogram.enums import ButtonStyle
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

S = ButtonStyle.SUCCESS
P = ButtonStyle.PRIMARY
D = ButtonStyle.DANGER

DEVICE_OPTIONS = [1, 2, 3, 4, 5]


def main_menu_keyboard(has_access: bool = True) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡️ Подключить VPN", callback_data="connect_vpn", style=S)],
        [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="topup", style=P)],
        [InlineKeyboardButton(text="📱 Мои устройства", callback_data="my_devices", style=P)],
        [InlineKeyboardButton(text="🔢 Число устройств", callback_data="change_devices", style=P)],
        [InlineKeyboardButton(text="📖 Инструкция", callback_data="instruction", style=P)],
        [InlineKeyboardButton(text="👥 Пригласить друзей", callback_data="referrals", style=P)],
        [InlineKeyboardButton(text="ℹ️ О сервисе", callback_data="about", style=P)],
        [InlineKeyboardButton(text="🆘 Поддержка", callback_data="support", style=P)],
    ])


def connect_vpn_keyboard(has_access: bool) -> InlineKeyboardMarkup:
    if has_access:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="topup", style=P)],
            [InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_menu", style=P)],
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="topup", style=P)],
        [InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_menu", style=P)],
    ])


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_menu", style=P)]
    ])


def referral_keyboard(ref_link: str) -> InlineKeyboardMarkup:
    share_url = f"https://t.me/share/url?url={ref_link}&text=Попробуй%20Zeus%20VPN%20—%20стабильный%20VPN"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Поделиться ссылкой", url=share_url, style=P)],
        [InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_menu", style=P)],
    ])


def support_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Написать в поддержку", url="https://t.me/zeus_vpnsupport", style=P)],
        [InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_menu", style=P)],
    ])


def terms_keyboard(privacy_url: str = "", user_agreement_url: str = "") -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text="✅ Принимаю условия", callback_data="accept_terms", style=S)]]
    if privacy_url:
        buttons.append([InlineKeyboardButton(text="Политика конфиденциальности", url=privacy_url, style=P)])
    if user_agreement_url:
        buttons.append([InlineKeyboardButton(text="Пользовательское соглашение", url=user_agreement_url, style=P)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def terms_accept_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принимаю условия", callback_data="accept_terms", style=S)],
        [InlineKeyboardButton(text="📄 Политика конфиденциальности", callback_data="about_privacy", style=P)],
        [InlineKeyboardButton(text="📋 Пользовательское соглашение", callback_data="about_terms", style=P)],
    ])


def about_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Политика конфиденциальности", callback_data="about_privacy", style=P)],
        [InlineKeyboardButton(text="📋 Пользовательское соглашение", callback_data="about_terms", style=P)],
        [InlineKeyboardButton(text="🆘 Контакты поддержки", callback_data="about_support", style=P)],
        [InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_menu", style=P)],
    ])


def about_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="about", style=P)],
    ])


def topup_amount_prompt_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Отмена", callback_data="back_to_menu", style=D)],
    ])


def payment_formed_keyboard(pay_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Оплатить", url=pay_url, style=S)],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_menu", style=D)],
    ])


def devices_count_keyboard(current: int) -> InlineKeyboardMarkup:
    buttons = []
    for n in DEVICE_OPTIONS:
        mark = "✅ " if n == current else ""
        buttons.append([InlineKeyboardButton(text=f"{mark}{n} устр", callback_data=f"set_devices:{n}", style=S if n == current else P)])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu", style=D)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
