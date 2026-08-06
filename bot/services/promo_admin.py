from datetime import datetime
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import PromoCode, PromoCodeUsage


async def create_promo(
    session: AsyncSession, code: str, amount: int, expires_str: str | None
) -> PromoCode:
    existing = await session.scalar(select(PromoCode).where(PromoCode.code == code))
    if existing:
        raise ValueError(f"Промокод {code} уже существует")
    expires_at = datetime.strptime(expires_str, "%Y-%m-%d") if expires_str else None
    promo = PromoCode(code=code, amount=amount, expires_at=expires_at)
    session.add(promo)
    await session.flush()
    return promo


async def list_promos(session: AsyncSession) -> tuple[list[PromoCode], dict[int, int]]:
    promos = (await session.scalars(
        select(PromoCode).where(PromoCode.is_active.is_(True))
    )).all()
    if not promos:
        return [], {}
    counts_rows = await session.execute(
        select(PromoCodeUsage.promo_code_id, func.count().label("cnt"))
        .where(PromoCodeUsage.promo_code_id.in_([p.id for p in promos]))
        .group_by(PromoCodeUsage.promo_code_id)
    )
    counts = {row.promo_code_id: row.cnt for row in counts_rows}
    return list(promos), counts


async def delete_promo(session: AsyncSession, code: str) -> bool:
    promo = await session.scalar(
        select(PromoCode).where(PromoCode.code == code, PromoCode.is_active.is_(True))
    )
    if promo is None:
        return False
    promo.is_active = False
    return True
