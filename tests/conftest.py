import os

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from bot.database.models import Base

os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("REMNAWAVE_URL", "https://example.test")
os.environ.setdefault("REMNAWAVE_API_TOKEN", "test-token")
os.environ.setdefault("YOOKASSA_SHOP_ID", "test_shop_id")
os.environ.setdefault("YOOKASSA_SECRET_KEY", "test_secret_key")
os.environ.setdefault("WEBHOOK_BASE_URL", "https://example.test")
os.environ.setdefault("WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("BOT_USERNAME", "test_bot")
os.environ.setdefault("SUBSCRIPTION_HOST", "https://test.example.com")

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

@pytest.fixture
async def db_session():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
