import asyncio
from decimal import Decimal
from sqlalchemy import func, select
from bot.database.session import AsyncSessionLocal
from bot.database.models import Plan

PLANS = [
    Plan(name="Базовый",  devices_limit=1, duration_days=30,  price=Decimal("149.00")),
    Plan(name="Базовый",  devices_limit=1, duration_days=90,  price=Decimal("399.00")),
    Plan(name="Базовый",  devices_limit=1, duration_days=180, price=Decimal("699.00")),
    Plan(name="Стандарт", devices_limit=3, duration_days=30,  price=Decimal("249.00")),
    Plan(name="Стандарт", devices_limit=3, duration_days=90,  price=Decimal("669.00")),
    Plan(name="Стандарт", devices_limit=3, duration_days=180, price=Decimal("1169.00")),
    Plan(name="Семейный", devices_limit=6, duration_days=30,  price=Decimal("399.00")),
    Plan(name="Семейный", devices_limit=6, duration_days=90,  price=Decimal("1069.00")),
    Plan(name="Семейный", devices_limit=6, duration_days=180, price=Decimal("1869.00")),
]


async def seed():
    async with AsyncSessionLocal() as session:
        existing = await session.scalar(select(func.count()).select_from(Plan))
        if existing:
            print(f"Plans already seeded ({existing} rows), skipping")
            return
        session.add_all(PLANS)
        await session.commit()
        print(f"Seeded {len(PLANS)} plans")


if __name__ == "__main__":
    asyncio.run(seed())
