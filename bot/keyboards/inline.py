from aiogram.enums import ButtonStyle
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

S = ButtonStyle.SUCCESS
P = ButtonStyle.PRIMARY
D = ButtonStyle.DANGER

PRICE_TABLE = {
    30:  {1: 149, 2: 249, 3: 399, 5: 599, 10: 1049},
    90:  {1: 399, 2: 599, 3: 1049, 5: 1849, 10: 3549},
    180: {1: 749, 2: 1049, 3: 1999, 5: 3599, 10: 7049},
    360: {1: 1249, 2: 1999, 3: 3649, 5: 5999, 10: 9999},
}
DEVICE_OPTIONS = [1, 2, 3, 5, 10]


def get_price(duration_days: int, devices: int) -> int:
    return PRICE_TABLE.get(duration_days, {}).get(devices, 0)


def main_menu_keyboard(has_sub: bool = False) -> InlineKeyboardMarkup:
    sub_btn = (
        InlineKeyboardButton(text="💎 Продлить подписку", callback_data="buy_subscription", style=P)
        if has_sub
        else InlineKeyboardButton(text="💎 Купить подписку", callback_data="buy_subscription", style=P)
    )
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡️ Подключить VPN", callback_data="connect_vpn", style=S)],
        [sub_btn],
        [InlineKeyboardButton(text="📱 Мои устройства", callback_data="my_devices")],
        [InlineKeyboardButton(text="📖 Инструкция", callback_data="instruction")],
        [InlineKeyboardButton(text="👥 Пригласить друзей", callback_data="referrals")],
        [InlineKeyboardButton(text="ℹ️ О сервисе", callback_data="about")],
        [InlineKeyboardButton(text="🆘 Поддержка", callback_data="support")],
    ])


def connect_vpn_keyboard(has_sub: bool) -> InlineKeyboardMarkup:
    if has_sub:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Продлить подписку", callback_data="buy_subscription", style=P)],
            [InlineKeyboardButton(text="➕ Добавить устройство", callback_data="add_devices", style=S)],
            [InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_menu")],
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Купить подписку", callback_data="buy_subscription", style=P)],
        [InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_menu")],
    ])


def plans_keyboard(plans: list) -> InlineKeyboardMarkup:
    _labels = {30: "30 дней", 90: "3 месяца", 180: "6 месяцев", 360: "1 год"}
    buttons = [
        [InlineKeyboardButton(
            text=f"{_labels.get(p.duration_days, f'{p.duration_days} дн.')} — от {get_price(p.duration_days, 1) or round(p.price)} ₽",
            callback_data=f"plan:{p.id}",
            style=P,
        )]
        for p in plans if p.duration_days > 0
    ]
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_menu")]
    ])


def referral_keyboard(ref_link: str) -> InlineKeyboardMarkup:
    share_url = f"https://t.me/share/url?url={ref_link}&text=Попробуй%20DS-VPN%20—%20стабильный%20VPN%20для%20России"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Поделиться ссылкой", url=share_url, style=P)],
        [InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_menu")],
    ])


def support_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Написать в поддержку", url="https://t.me/ds_vpnsupport", style=P)],
        [InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_menu")],
    ])


def terms_keyboard(privacy_url: str = "", user_agreement_url: str = "") -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text="✅ Принимаю условия", callback_data="accept_terms", style=S)]]
    if privacy_url:
        buttons.append([InlineKeyboardButton(text="Политика конфиденциальности", url=privacy_url)])
    if user_agreement_url:
        buttons.append([InlineKeyboardButton(text="Пользовательское соглашение", url=user_agreement_url)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def terms_accept_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принимаю условия", callback_data="accept_terms", style=S)],
        [InlineKeyboardButton(text="📄 Политика конфиденциальности", callback_data="about_privacy")],
        [InlineKeyboardButton(text="📋 Пользовательское соглашение", callback_data="about_terms")],
    ])


def about_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Политика конфиденциальности", callback_data="about_privacy")],
        [InlineKeyboardButton(text="📋 Пользовательское соглашение", callback_data="about_terms")],
        [InlineKeyboardButton(text="🆘 Контакты поддержки", callback_data="about_support")],
        [InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_menu")],
    ])


def about_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="about")],
    ])


def devices_select_keyboard(plan_id: int, duration_days: int) -> InlineKeyboardMarkup:
    buttons = []
    for d in DEVICE_OPTIONS:
        total = get_price(duration_days, d)
        buttons.append([InlineKeyboardButton(
            text=f"💎 {d} устр — {total} ₽",
            callback_data=f"order:{plan_id}:{d}",
            style=P,
        )])
    buttons.append([InlineKeyboardButton(text="◀ Назад", callback_data="buy_subscription")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def order_confirm_keyboard(
    plan_id: int, devices: int, promo_applied: bool = False, promo_str: str = ""
) -> InlineKeyboardMarkup:
    promo_btn = (
        InlineKeyboardButton(
            text=f"✖ Убрать промокод ({promo_str})",
            callback_data=f"promo_cancel_order:{plan_id}:{devices}",
            style=D,
        )
        if promo_applied
        else InlineKeyboardButton(
            text="🏷 Промокод",
            callback_data=f"promo_apply_order:{plan_id}:{devices}",
        )
    )
    return InlineKeyboardMarkup(inline_keyboard=[
        [promo_btn],
        [InlineKeyboardButton(
            text="✅ Перейти к оплате",
            callback_data=f"confirm_pay:{plan_id}:{devices}",
            style=S,
        )],
        [InlineKeyboardButton(text="◀ Назад", callback_data=f"plan:{plan_id}")],
    ])


def payment_formed_keyboard(pay_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Оплатить", url=pay_url, style=S)],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="buy_subscription", style=D)],
    ])


def upgrade_devices_keyboard(
    duration_days: int, current_devices: int, remaining_days: int, total_days: int
) -> InlineKeyboardMarkup:
    buttons = []
    cur_price = get_price(duration_days, current_devices)
    for d in DEVICE_OPTIONS:
        if d <= current_devices:
            continue
        new_price = get_price(duration_days, d)
        if not new_price:
            continue
        upgrade_cost = max(1, round((new_price - cur_price) * remaining_days / max(total_days, 1)))
        buttons.append([InlineKeyboardButton(
            text=f"💎 {d} устр — доплата {upgrade_cost} ₽",
            callback_data=f"upgrade_to:{d}",
            style=P,
        )])
    buttons.append([InlineKeyboardButton(text="◀ Назад", callback_data="connect_vpn")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
