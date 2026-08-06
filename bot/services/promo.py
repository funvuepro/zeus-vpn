from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import PromoCode, PromoCodeUsage


def _is_expired(expires_at: datetime) -> bool:
    # SQLite returns naive datetimes; treat them as UTC
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at < datetime.now(timezone.utc)


async def validate_promo(
    session: AsyncSession, code_str: str, user_id: int
) -> tuple[PromoCode | None, str | None]:
    promo = await session.scalar(
        select(PromoCode).where(PromoCode.code == code_str.upper(), PromoCode.is_active.is_(True))
    )
    if promo is None:
        return None, "❌ Промокод не найден или недействителен"
    if promo.expires_at is not None and _is_expired(promo.expires_at):
        return None, "❌ Срок действия промокода истёк"
    usage = await session.scalar(
        select(PromoCodeUsage).where(
            PromoCodeUsage.promo_code_id == promo.id,
            PromoCodeUsage.user_id == user_id,
        )
    )
    if usage is not None:
        return None, "❌ Ты уже использовал этот промокод"
    return promo, None


async def record_usage(session: AsyncSession, promo_code_id: int, user_id: int) -> None:
    session.add(PromoCodeUsage(promo_code_id=promo_code_id, user_id=user_id))
