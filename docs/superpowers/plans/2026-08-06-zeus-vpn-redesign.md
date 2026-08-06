# Zeus VPN Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up Zeus VPN as an independent project cloned from `VpnBot`, with a new brand, a YooKassa-based payment intake, and a full switch from fixed-duration Plan/Subscription billing to a balance + per-device daily-charge model with a flat one-time referral bonus.

**Architecture:** Same stack as `VpnBot` (aiogram + FastAPI + SQLAlchemy/Alembic + Remnawave + APScheduler). The billing engine changes from "buy N days" to "hold a balance, debit it once a day"; `Plan`/`Subscription`/`Withdrawal`/`ReferralTransaction` are deleted and replaced by fields on `User` plus a singleton `AppSettings` row for the admin-tunable daily rate.

**Tech Stack:** Python 3.12, aiogram 3, FastAPI, SQLAlchemy 2 (async) + Alembic, httpx, pytest + pytest-asyncio, Remnawave HTTP API, YooKassa REST API v3.

## Global Constraints

- Source of truth for all decisions below: `docs/superpowers/specs/2026-08-06-zeus-vpn-redesign-design.md`. Where this plan and that spec disagree, the spec wins — stop and flag it.
- Brand name is **Zeus VPN** everywhere user-facing (replaces `DS-VPN`). Support handle is `@zeus_vpnsupport` (placeholder).
- Daily rate formula (fixed, do not change without spec update): `charge = daily_rate_per_device * 0.5 * (devices_limit + 1)`.
- Minimum top-up amount is **100 RUB** (`settings.MIN_TOPUP_RUB`), enforced before any YooKassa call.
- Grace period on zero balance: warn 1 day before zero (i.e. when the *next* charge would take balance to/below zero), then 24 hours of continued access once balance is actually ≤ 0, then disable.
- Referral bonus is a **flat 100 RUB**, credited once, on the referred user's first successful top-up — never a percentage, never repeatable.
- `VpnBot` (the old project at `C:\Projects\VpnBot`) is never modified by this plan.
- No real secrets (`YOOKASSA_SHOP_ID`, `YOOKASSA_SECRET_KEY`, `BOT_TOKEN`, `REMNAWAVE_*`) are hardcoded; all come from `.env`, which is never committed.
- Every task that touches Python code ends with `pytest -q` passing for the whole suite, not just the new test file — regressions in earlier tasks must be caught immediately.

---

## File Structure Overview

```
новый VPN/
├── bot/
│   ├── config.py                  # Settings: YOOKASSA_*, MIN_TOPUP_RUB; drop CRYPTOBOT/LAVA/FREEKASSA/REFERRAL_PERCENT
│   ├── database/models.py         # User balance fields, AppSettings, trimmed Payment/PaymentProvider, drops Plan/Subscription/Withdrawal*/ReferralTransaction
│   ├── migrations/versions/       # new Alembic revision
│   ├── services/
│   │   ├── balance.py             # NEW: daily rate calc, AppSettings get/set, credit_topup()
│   │   ├── yookassa.py            # NEW: create_payment(), get_payment_status()
│   │   ├── referral.py            # REWRITE: grant_referral_bonus(), drop withdrawal code
│   │   ├── remnawave.py           # unchanged
│   │   ├── subscription.py        # DELETED (activate_subscription logic replaced by balance.credit_topup)
│   │   ├── cryptobot.py / lava.py / freekassa.py   # DELETED
│   ├── webhooks/
│   │   ├── yookassa.py            # NEW
│   │   ├── app.py                 # wire in yookassa router, drop cryptobot/lava/freekassa
│   │   ├── cryptobot.py / lava.py / freekassa.py   # DELETED
│   ├── scheduler/tasks.py         # REWRITE: run_daily_billing() replaces the 3 expiry-based jobs
│   ├── handlers/
│   │   ├── start.py               # registration seeds balance/devices_limit, menu text shows balance
│   │   ├── menu.py                # connect_vpn/back_to_menu/support use User fields, add_devices removed
│   │   ├── payment.py             # REWRITE: top-up flow + device-count change (was plan purchase)
│   │   ├── subscription.py        # DELETED (plan picker)
│   │   ├── devices.py             # Subscription.devices_limit -> User.devices_limit
│   │   ├── referral.py            # balance-based stats, no withdrawal
│   │   ├── admin.py               # drop Plan/Subscription admin flows, add rate-setting
│   │   ├── promo.py               # promo redemption credits balance instead of discounting an order
│   │   └── about.py               # brand text
│   ├── keyboards/
│   │   ├── inline.py              # drop plan/order/upgrade keyboards, add topup/devices-count keyboards
│   │   └── admin.py                # drop Plan/Subscription admin keyboards, add rate-setting keyboard
│   └── main.py                    # _init_db reseed, scheduler wiring, brand strings
├── .env.example                   # YOOKASSA_*, MIN_TOPUP_RUB, no old provider vars
└── tests/                         # new/updated coverage per task below
```

---

### Task 1: Bootstrap Zeus VPN project from the VpnBot base

**Files:**
- Create: entire tree under `C:\Projects\новый VPN` (copy of `C:\Projects\VpnBot`)
- Create: `C:\Projects\новый VPN\.gitignore` (copy from VpnBot)

**Interfaces:** none (scaffolding task).

- [ ] **Step 1: Copy the source tree, excluding local/generated artifacts**

Run (PowerShell, from `C:\Projects`):

```powershell
robocopy "VpnBot" "новый VPN" /E /XD .git .venv __pycache__ .pytest_cache /XF test.db "Снимок экрана 2026-06-04 в 10.31.08 PM.png"
```

`robocopy` exits with codes 0–7 on success (not just 0) — treat exit code ≥8 as failure.

- [ ] **Step 2: Verify no excluded artifacts leaked through**

Run: `Get-ChildItem -Recurse "новый VPN" -Include .git,.venv,__pycache__,.pytest_cache,test.db -Force`
Expected: empty output.

- [ ] **Step 3: Create a fresh virtualenv and install dependencies**

```powershell
cd "C:\Projects\новый VPN"
python -m venv .venv
.\.venv\Scripts\pip install poetry
.\.venv\Scripts\poetry install
```

- [ ] **Step 4: Run the inherited test suite as a baseline — it must pass unmodified**

Run: `.\.venv\Scripts\pytest -q`
Expected: all tests pass (same pass count as `VpnBot` had before the copy). This is the safety net for every later task.

- [ ] **Step 5: Init git and commit the untouched baseline**

```powershell
git init
git add -A
git commit -m "chore: bootstrap Zeus VPN from VpnBot base"
```

---

### Task 2: Rebrand config and environment

**Files:**
- Modify: `bot/config.py`
- Modify: `.env.example`
- Modify: `tests/conftest.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Settings.YOOKASSA_SHOP_ID: str`, `Settings.YOOKASSA_SECRET_KEY: str`, `Settings.MIN_TOPUP_RUB: float` — every later task that talks to YooKassa or validates top-up amount reads these.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
import os

def test_settings_has_yookassa_and_no_legacy_providers(monkeypatch):
    monkeypatch.setenv("YOOKASSA_SHOP_ID", "shop_123")
    monkeypatch.setenv("YOOKASSA_SECRET_KEY", "secret_abc")
    from bot.config import Settings
    s = Settings()
    assert s.YOOKASSA_SHOP_ID == "shop_123"
    assert s.YOOKASSA_SECRET_KEY == "secret_abc"
    assert s.MIN_TOPUP_RUB == 100.0
    assert not hasattr(s, "CRYPTOBOT_TOKEN")
    assert not hasattr(s, "LAVA_API_KEY")
    assert not hasattr(s, "FREEKASSA_SHOP_ID")
    assert not hasattr(s, "REFERRAL_PERCENT")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL (`ImportError` or `AttributeError` — old `Settings` still has the legacy fields and lacks the new ones).

- [ ] **Step 3: Rewrite `bot/config.py`**

```python
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    BOT_TOKEN: str
    DATABASE_URL: str
    REMNAWAVE_URL: str
    REMNAWAVE_API_TOKEN: str
    SUBSCRIPTION_HOST: str = ""
    YOOKASSA_SHOP_ID: str = ""
    YOOKASSA_SECRET_KEY: str = ""
    MIN_TOPUP_RUB: float = 100.0
    WEBHOOK_BASE_URL: str
    WEBHOOK_SECRET: str
    BOT_USERNAME: str
    PRIVACY_URL: str = ""
    USER_AGREEMENT_URL: str = ""

    model_config = SettingsConfigDict(env_file=".env")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
```

- [ ] **Step 4: Update `tests/conftest.py` env defaults**

Replace the `os.environ.setdefault("CRYPTOBOT_TOKEN", ...)` line with:

```python
os.environ.setdefault("YOOKASSA_SHOP_ID", "test_shop_id")
os.environ.setdefault("YOOKASSA_SECRET_KEY", "test_secret_key")
```

- [ ] **Step 5: Update `.env.example`**

```
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ
DATABASE_URL=postgresql+asyncpg://zeusvpn:password@localhost:5432/zeusvpn
REMNAWAVE_URL=https://yourserver.com
REMNAWAVE_API_TOKEN=your_remnawave_api_token
SUBSCRIPTION_HOST=
YOOKASSA_SHOP_ID=
YOOKASSA_SECRET_KEY=
MIN_TOPUP_RUB=100.0
WEBHOOK_BASE_URL=https://yourdomain.com/webhook
WEBHOOK_SECRET=random_secret_string_32chars
BOT_USERNAME=your_bot_username_without_at
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS.

- [ ] **Step 7: Run full suite (some old tests still reference removed fields — expected to fail until later tasks; confirm the failures are only in payment-provider tests)**

Run: `pytest -q`
Expected: failures limited to `tests/test_webhooks/test_cryptobot_webhook.py` (import/env errors) — note this, it gets deleted in Task 7.

- [ ] **Step 8: Commit**

```bash
git add bot/config.py .env.example tests/conftest.py tests/test_config.py
git commit -m "feat: rebrand settings for YooKassa, drop legacy payment config"
```

---

### Task 3: Database models — balance system, drop legacy tables

**Files:**
- Modify: `bot/database/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces: `User.balance: Decimal`, `User.devices_limit: int`, `User.access_active: bool`, `User.grace_started_at: datetime | None`, `User.referral_bonus_granted: bool`; `AppSettings.daily_rate_per_device: Decimal`; `PaymentProvider.yookassa`; `Payment.external_id/amount/status/user_id/provider`.
- Removes: `Plan`, `Subscription`, `SubscriptionStatus`, `Withdrawal`, `WithdrawalProvider`, `WithdrawalStatus`, `CryptoType`, `ReferralTransaction`, `ReferralStatus`, and `Payment.plan_id/subscription_id/devices_count/is_upgrade/promo_code_id`, `User.bonus_days`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py
from decimal import Decimal
from bot.database.models import Base, User, AppSettings, Payment, PaymentProvider, PaymentStatus


async def test_user_has_balance_fields(db_session):
    user = User(telegram_id=1, username="u")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    assert user.balance == Decimal("0.00")
    assert user.devices_limit == 1
    assert user.access_active is True
    assert user.grace_started_at is None
    assert user.referral_bonus_granted is False


async def test_app_settings_default_rate(db_session):
    row = AppSettings(id=1, daily_rate_per_device=Decimal("1.00"))
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    assert row.daily_rate_per_device == Decimal("1.00")


async def test_payment_provider_only_yookassa():
    assert [p.value for p in PaymentProvider] == ["yookassa"]


async def test_legacy_models_removed():
    import bot.database.models as m
    for name in ("Plan", "Subscription", "Withdrawal", "WithdrawalProvider", "ReferralTransaction"):
        assert not hasattr(m, name), f"{name} should have been removed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL (`AttributeError: 'User' object has no attribute 'balance'`, etc).

- [ ] **Step 3: Rewrite `bot/database/models.py`**

```python
import enum
from sqlalchemy import BigInteger, Boolean, Column, DateTime, Enum, ForeignKey, Numeric, String, Integer, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class PaymentStatus(enum.Enum):
    pending = "pending"
    paid = "paid"
    failed = "failed"


class PaymentProvider(enum.Enum):
    yookassa = "yookassa"


class InstructionPlatform(enum.Enum):
    android = "android"
    ios = "ios"
    windows = "windows"
    macos = "macos"


class InstructionCategory(enum.Enum):
    general = "general"
    connect = "connect"


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String, nullable=True)
    remnawave_uuid = Column(String, unique=True, nullable=True)
    referred_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    display_id = Column(Integer, unique=True, nullable=True)
    balance = Column(Numeric(10, 2), nullable=False, default=0, server_default="0")
    devices_limit = Column(Integer, nullable=False, default=1, server_default="1")
    access_active = Column(Boolean, nullable=False, default=True, server_default="true")
    grace_started_at = Column(DateTime(timezone=True), nullable=True)
    referral_bonus_granted = Column(Boolean, nullable=False, default=False, server_default="false")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_banned = Column(Boolean, nullable=False, server_default="false", default=False)
    is_admin = Column(Boolean, default=False, nullable=False, server_default="false")
    terms_accepted = Column(Boolean, default=False, nullable=False, server_default="false")
    terms_accepted_at = Column(DateTime(timezone=True), nullable=True)


class AppSettings(Base):
    __tablename__ = "app_settings"
    id = Column(Integer, primary_key=True)
    daily_rate_per_device = Column(Numeric(10, 2), nullable=False, default="1.00", server_default="1.00")


class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    provider = Column(Enum(PaymentProvider), nullable=False)
    external_id = Column(String, unique=True, nullable=True)
    amount = Column(Numeric(10, 2), nullable=False)
    status = Column(Enum(PaymentStatus), default=PaymentStatus.pending, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PromoCode(Base):
    __tablename__ = "promo_codes"

    id = Column(Integer, primary_key=True)
    code = Column(String(32), unique=True, nullable=False)
    amount = Column(Integer, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PromoCodeUsage(Base):
    __tablename__ = "promo_code_usages"

    id = Column(Integer, primary_key=True)
    promo_code_id = Column(Integer, ForeignKey("promo_codes.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    used_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("promo_code_id", "user_id", name="uq_promo_usage"),)


class Instruction(Base):
    __tablename__ = "instructions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(Enum(InstructionPlatform), nullable=False)
    category = Column(Enum(InstructionCategory), nullable=False, default=InstructionCategory.general)
    text = Column(String, nullable=False)
    __table_args__ = (UniqueConstraint("platform", "category", name="uq_instruction_platform_category"),)


class VpnServer(Base):
    __tablename__ = "vpn_servers"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    ip = Column(String, nullable=False)
    port = Column(Integer, nullable=False, default=443)
    transport = Column(String, nullable=False, default="tcp")
    public_key = Column(String, nullable=False)
    short_id = Column(String, nullable=False)
    server_name = Column(String, nullable=False)
    fingerprint = Column(String, nullable=False, default="firefox")
    service_name = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    is_backup = Column(Boolean, nullable=False, default=False, server_default="false")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bot/database/models.py tests/test_models.py
git commit -m "feat: replace Plan/Subscription billing model with balance fields"
```

---

### Task 4: Alembic migration for the new schema

**Files:**
- Create: `bot/migrations/versions/<hash>_zeus_vpn_balance_model.py`

**Interfaces:**
- Consumes: `bot/database/models.py` (Task 3) as the target schema.

- [ ] **Step 1: Generate the revision skeleton**

```powershell
.\.venv\Scripts\alembic revision -m "zeus vpn balance model"
```

- [ ] **Step 2: Write `upgrade()`/`downgrade()`**

```python
"""zeus vpn balance model

Revision ID: <generated>
Revises: 7809f86894f4
Create Date: 2026-08-06
"""
from alembic import op
import sqlalchemy as sa

revision = "<generated>"
down_revision = "7809f86894f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("balance", sa.Numeric(10, 2), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("devices_limit", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("users", sa.Column("access_active", sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("users", sa.Column("grace_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("referral_bonus_granted", sa.Boolean(), nullable=False, server_default="false"))
    op.drop_column("users", "bonus_days")

    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("daily_rate_per_device", sa.Numeric(10, 2), nullable=False, server_default="1.00"),
    )
    op.execute("INSERT INTO app_settings (id, daily_rate_per_device) VALUES (1, 1.00)")

    op.drop_table("withdrawals")
    op.drop_table("referral_transactions")
    op.drop_table("subscriptions")

    op.drop_column("payments", "plan_id")
    op.drop_column("payments", "subscription_id")
    op.drop_column("payments", "devices_count")
    op.drop_column("payments", "is_upgrade")
    op.drop_column("payments", "promo_code_id")

    op.drop_table("plans")

    op.execute("ALTER TYPE paymentprovider RENAME TO paymentprovider_old")
    op.execute("CREATE TYPE paymentprovider AS ENUM ('yookassa')")
    op.execute(
        "ALTER TABLE payments ALTER COLUMN provider TYPE paymentprovider "
        "USING 'yookassa'::paymentprovider"
    )
    op.execute("DROP TYPE paymentprovider_old")
    op.execute("DROP TYPE IF EXISTS withdrawalprovider")
    op.execute("DROP TYPE IF EXISTS withdrawalstatus")
    op.execute("DROP TYPE IF EXISTS cryptotype")
    op.execute("DROP TYPE IF EXISTS referralstatus")
    op.execute("DROP TYPE IF EXISTS subscriptionstatus")


def downgrade() -> None:
    raise NotImplementedError("Zeus VPN is a fresh project — no downgrade path from the new model")
```

- [ ] **Step 3: Verify the migration applies cleanly against Postgres**

Run against a throwaway Postgres instance (Docker):

```powershell
docker run --rm -d --name zeusvpn-migtest -e POSTGRES_PASSWORD=test -e POSTGRES_DB=zeusvpn_test -p 55432:5432 postgres:16
$env:DATABASE_URL = "postgresql+asyncpg://postgres:test@localhost:55432/zeusvpn_test"
.\.venv\Scripts\alembic upgrade head
docker stop zeusvpn-migtest
```

Expected: `alembic upgrade head` exits 0, no errors.

- [ ] **Step 4: Commit**

```bash
git add bot/migrations/versions/
git commit -m "feat: add migration for balance model schema"
```

---

### Task 5: Balance service — daily rate calculation and settings store

**Files:**
- Create: `bot/services/balance.py`
- Test: `tests/test_services/test_balance.py`

**Interfaces:**
- Produces: `calculate_daily_charge(daily_rate: Decimal, devices_limit: int) -> Decimal`, `get_daily_rate_per_device(session) -> Decimal`, `set_daily_rate_per_device(session, value: Decimal) -> None`, `credit_topup(payment_id: int, amount: Decimal, external_id: str, session) -> None`, `notify_user(telegram_id: int, text: str)` (reassigned at startup like the old `subscription.notify_user`).
- Consumes: `bot.services.remnawave.remnawave.enable_user()` (unchanged from VpnBot). `bot.services.referral.grant_referral_bonus()` is wired into `credit_topup` later, in Task 8 Step 5 — not part of this task's deliverable.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_services/test_balance.py
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from bot.database.models import AppSettings, Payment, PaymentProvider, PaymentStatus, User
from bot.services.balance import (
    calculate_daily_charge,
    get_daily_rate_per_device,
    set_daily_rate_per_device,
    credit_topup,
)


def test_calculate_daily_charge_scales_with_devices():
    rate = Decimal("1.00")
    assert calculate_daily_charge(rate, 1) == Decimal("1.00")
    assert calculate_daily_charge(rate, 2) == Decimal("1.50")
    assert calculate_daily_charge(rate, 3) == Decimal("2.00")


async def test_get_daily_rate_defaults_when_unset(db_session):
    rate = await get_daily_rate_per_device(db_session)
    assert rate == Decimal("1.00")


async def test_set_then_get_daily_rate(db_session):
    await set_daily_rate_per_device(db_session, Decimal("2.50"))
    rate = await get_daily_rate_per_device(db_session)
    assert rate == Decimal("2.50")


async def test_credit_topup_adds_balance_and_marks_paid(db_session):
    user = User(telegram_id=500, username="topupper", balance=Decimal("0.00"))
    db_session.add(user)
    await db_session.commit()

    payment = Payment(user_id=user.id, provider=PaymentProvider.yookassa, amount=Decimal("150.00"))
    db_session.add(payment)
    await db_session.commit()

    await credit_topup(payment.id, Decimal("150.00"), "yk_ext_1", db_session)

    await db_session.refresh(user)
    await db_session.refresh(payment)
    assert user.balance == Decimal("150.00")
    assert payment.status == PaymentStatus.paid
    assert payment.external_id == "yk_ext_1"


async def test_credit_topup_is_idempotent(db_session):
    user = User(telegram_id=501, username="twice", balance=Decimal("0.00"))
    db_session.add(user)
    await db_session.commit()

    payment = Payment(user_id=user.id, provider=PaymentProvider.yookassa, amount=Decimal("150.00"))
    db_session.add(payment)
    await db_session.commit()

    await credit_topup(payment.id, Decimal("150.00"), "yk_ext_1", db_session)
    await credit_topup(payment.id, Decimal("150.00"), "yk_ext_1", db_session)

    await db_session.refresh(user)
    assert user.balance == Decimal("150.00")  # not credited twice


async def test_credit_topup_reactivates_disabled_access(db_session):
    from datetime import datetime, timezone
    user = User(
        telegram_id=502, username="reactivate", balance=Decimal("0.00"),
        access_active=False, grace_started_at=datetime.now(timezone.utc),
        remnawave_uuid="uuid-1",
    )
    db_session.add(user)
    await db_session.commit()

    payment = Payment(user_id=user.id, provider=PaymentProvider.yookassa, amount=Decimal("100.00"))
    db_session.add(payment)
    await db_session.commit()

    with patch("bot.services.balance.remnawave") as mock_remnawave:
        mock_remnawave.enable_user = AsyncMock()
        await credit_topup(payment.id, Decimal("100.00"), "yk_ext_2", db_session)
        mock_remnawave.enable_user.assert_called_once_with("uuid-1")

    await db_session.refresh(user)
    assert user.access_active is True
    assert user.grace_started_at is None
```

Note: this task deliberately does **not** wire the referral bonus yet — `bot/services/referral.py` still contains the old withdrawal-era code at this point in the plan and can't be imported safely. Task 8 rewrites `referral.py` and adds the one-line hook into `credit_topup`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_services/test_balance.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'bot.services.balance'`).

- [ ] **Step 3: Write `bot/services/balance.py`**

```python
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import AppSettings, Payment, PaymentStatus, User
from bot.services.remnawave import remnawave

DEFAULT_DAILY_RATE = Decimal("1.00")


async def notify_user(telegram_id: int, text: str):
    pass  # reassigned at startup in main.py


def calculate_daily_charge(daily_rate_per_device: Decimal, devices_limit: int) -> Decimal:
    multiplier = Decimal("0.5") * (Decimal(devices_limit) + 1)
    return (daily_rate_per_device * multiplier).quantize(Decimal("0.01"))


async def get_daily_rate_per_device(session: AsyncSession) -> Decimal:
    row = await session.get(AppSettings, 1)
    return row.daily_rate_per_device if row else DEFAULT_DAILY_RATE


async def set_daily_rate_per_device(session: AsyncSession, value: Decimal) -> None:
    row = await session.get(AppSettings, 1)
    if row is None:
        session.add(AppSettings(id=1, daily_rate_per_device=value))
    else:
        row.daily_rate_per_device = value
    await session.commit()


async def credit_topup(payment_id: int, amount: Decimal, external_id: str, session: AsyncSession) -> None:
    result = await session.execute(
        update(Payment)
        .where(Payment.id == payment_id, Payment.status == PaymentStatus.pending)
        .values(status=PaymentStatus.paid, external_id=external_id)
        .returning(Payment)
    )
    payment = result.scalar_one_or_none()
    if payment is None:
        return  # already credited or unknown payment id

    user = await session.get(User, payment.user_id)
    user.balance += amount

    if user.grace_started_at is not None:
        user.grace_started_at = None
    if not user.access_active:
        user.access_active = True
        if user.remnawave_uuid:
            await remnawave.enable_user(user.remnawave_uuid)

    await session.commit()
    await notify_user(user.telegram_id, f"⚡ Баланс пополнен на {amount} ₽. Текущий баланс: {user.balance} ₽")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_services/test_balance.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bot/services/balance.py tests/test_services/test_balance.py
git commit -m "feat: add balance service with daily rate calc and top-up crediting"
```

---

### Task 6: YooKassa payment service

**Files:**
- Create: `bot/services/yookassa.py`
- Test: `tests/test_services/test_yookassa.py`
- Delete: `bot/services/cryptobot.py`, `bot/services/lava.py`, `bot/services/freekassa.py`

**Interfaces:**
- Produces: `create_payment(amount_rub: float, payment_id: int, description: str) -> str`, `get_payment_status(yookassa_payment_id: str) -> dict`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_services/test_yookassa.py
from unittest.mock import AsyncMock, MagicMock

import bot.services.yookassa as yk


def _mock_async_client(monkeypatch, response_json, method="post"):
    mock_resp = MagicMock()
    mock_resp.json.return_value = response_json
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    setattr(mock_client, method, AsyncMock(return_value=mock_resp))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(yk.httpx, "AsyncClient", lambda **kw: mock_client)
    return mock_client


async def test_create_payment_returns_confirmation_url(monkeypatch):
    mock_client = _mock_async_client(monkeypatch, {
        "id": "yk_1", "confirmation": {"confirmation_url": "https://yookassa.ru/pay/abc"},
    }, method="post")

    url = await yk.create_payment(150.0, 42, "Пополнение баланса Zeus VPN")

    assert url == "https://yookassa.ru/pay/abc"
    call = mock_client.post.call_args
    assert call.args[0] == f"{yk.YOOKASSA_API}/payments"
    body = call.kwargs["json"]
    assert body["amount"] == {"value": "150.00", "currency": "RUB"}
    assert body["metadata"] == {"payment_id": "42"}
    assert "Idempotence-Key" in call.kwargs["headers"]


async def test_get_payment_status_returns_full_payload(monkeypatch):
    payload = {"id": "yk_1", "status": "succeeded", "amount": {"value": "150.00", "currency": "RUB"}}
    mock_client = _mock_async_client(monkeypatch, payload, method="get")

    result = await yk.get_payment_status("yk_1")

    assert result == payload
    call = mock_client.get.call_args
    assert call.args[0] == f"{yk.YOOKASSA_API}/payments/yk_1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_services/test_yookassa.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write `bot/services/yookassa.py`**

```python
import uuid

import httpx

from bot.config import get_settings

YOOKASSA_API = "https://api.yookassa.ru/v3"


async def create_payment(amount_rub: float, payment_id: int, description: str) -> str:
    s = get_settings()
    idempotence_key = f"{payment_id}-{uuid.uuid4()}"
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{YOOKASSA_API}/payments",
            auth=(s.YOOKASSA_SHOP_ID, s.YOOKASSA_SECRET_KEY),
            headers={"Idempotence-Key": idempotence_key},
            json={
                "amount": {"value": f"{amount_rub:.2f}", "currency": "RUB"},
                "confirmation": {"type": "redirect", "return_url": f"https://t.me/{s.BOT_USERNAME}"},
                "capture": True,
                "description": description,
                "metadata": {"payment_id": str(payment_id)},
            },
        )
        resp.raise_for_status()
        return resp.json()["confirmation"]["confirmation_url"]


async def get_payment_status(yookassa_payment_id: str) -> dict:
    s = get_settings()
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{YOOKASSA_API}/payments/{yookassa_payment_id}",
            auth=(s.YOOKASSA_SHOP_ID, s.YOOKASSA_SECRET_KEY),
        )
        resp.raise_for_status()
        return resp.json()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_services/test_yookassa.py -v`
Expected: PASS.

- [ ] **Step 5: Delete the old provider services and their now-orphaned tests**

```bash
git rm bot/services/cryptobot.py bot/services/lava.py bot/services/freekassa.py
```

(No dedicated test files existed for these — confirmed via `tests/test_services/` listing — so no test deletions needed here.)

- [ ] **Step 6: Commit**

```bash
git add bot/services/yookassa.py tests/test_services/test_yookassa.py
git commit -m "feat: add YooKassa payment service, remove legacy providers"
```

---

### Task 7: YooKassa webhook

**Files:**
- Create: `bot/webhooks/yookassa.py`
- Modify: `bot/webhooks/app.py`
- Delete: `bot/webhooks/cryptobot.py`, `bot/webhooks/lava.py`, `bot/webhooks/freekassa.py`
- Delete: `tests/test_webhooks/test_cryptobot_webhook.py`
- Create: `tests/test_webhooks/test_yookassa_webhook.py`

**Interfaces:**
- Consumes: `bot.services.yookassa.get_payment_status()` (Task 6), `bot.services.balance.credit_topup()` (Task 5).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_webhooks/test_yookassa_webhook.py
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from bot.webhooks.app import create_app


@pytest.fixture
def app(db_session):
    return create_app(session_factory=lambda: db_session)


async def test_payment_succeeded_credits_balance(app, db_session):
    from bot.database.models import User, Payment, PaymentProvider

    user = User(telegram_id=900, username="payer")
    db_session.add(user)
    await db_session.commit()

    payment = Payment(user_id=user.id, provider=PaymentProvider.yookassa, amount=Decimal("150.00"))
    db_session.add(payment)
    await db_session.commit()

    webhook_body = {
        "event": "payment.succeeded",
        "object": {"id": "yk_ext_99"},
    }
    status_response = {
        "id": "yk_ext_99",
        "status": "succeeded",
        "amount": {"value": "150.00", "currency": "RUB"},
        "metadata": {"payment_id": str(payment.id)},
    }

    with patch("bot.webhooks.yookassa.get_payment_status", new_callable=AsyncMock) as mock_status:
        mock_status.return_value = status_response
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/webhook/yookassa", json=webhook_body)

    assert resp.status_code == 200
    await db_session.refresh(user)
    assert user.balance == Decimal("150.00")


async def test_non_succeeded_event_is_ignored(app, db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/webhook/yookassa", json={"event": "payment.canceled", "object": {"id": "x"}})
    assert resp.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_webhooks/test_yookassa_webhook.py -v`
Expected: FAIL (`404 Not Found` — route doesn't exist yet).

- [ ] **Step 3: Write `bot/webhooks/yookassa.py`**

```python
from decimal import Decimal

from fastapi import APIRouter, Request

from bot.services.yookassa import get_payment_status
from bot.services.balance import credit_topup

router = APIRouter()


@router.post("/webhook/yookassa")
async def yookassa_webhook(request: Request):
    data = await request.json()
    if data.get("event") != "payment.succeeded":
        return {"ok": True}

    yookassa_payment_id = data.get("object", {}).get("id")
    if not yookassa_payment_id:
        return {"ok": True}

    status_data = await get_payment_status(yookassa_payment_id)
    if status_data.get("status") != "succeeded":
        return {"ok": True}

    payment_id = status_data.get("metadata", {}).get("payment_id")
    if not payment_id:
        return {"ok": True}

    amount = Decimal(status_data["amount"]["value"])
    async with request.app.state.session_factory() as session:
        await credit_topup(int(payment_id), amount, yookassa_payment_id, session)
    return {"ok": True}
```

- [ ] **Step 4: Wire it into `bot/webhooks/app.py`**

```python
from fastapi import FastAPI

from bot.database.session import AsyncSessionLocal


def create_app(session_factory=None) -> FastAPI:
    app = FastAPI()
    app.state.session_factory = session_factory or AsyncSessionLocal

    from bot.webhooks.yookassa import router as yookassa_router
    from bot.webhooks.subscription import router as sub_router

    app.include_router(yookassa_router)
    app.include_router(sub_router)

    return app


app = create_app()
```

- [ ] **Step 5: Delete the old webhook modules and their test**

```bash
git rm bot/webhooks/cryptobot.py bot/webhooks/lava.py bot/webhooks/freekassa.py
git rm tests/test_webhooks/test_cryptobot_webhook.py
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_webhooks/test_yookassa_webhook.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add bot/webhooks/yookassa.py bot/webhooks/app.py tests/test_webhooks/test_yookassa_webhook.py
git commit -m "feat: add YooKassa webhook, remove legacy payment webhooks"
```

---

### Task 8: Referral service — flat bonus, drop withdrawal

**Files:**
- Rewrite: `bot/services/referral.py`
- Test: `tests/test_services/test_referral.py`

**Interfaces:**
- Produces: `grant_referral_bonus(user: User, session) -> None`, `get_referral_registered_count(user_id, session) -> int`, `get_referral_paid_count(user_id, session) -> int`.
- Consumed by: `bot.services.balance.credit_topup()` (Task 5) — wired in Step 5 of this task, once `referral.py` is safe to import.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_services/test_referral.py
from decimal import Decimal

from bot.database.models import Payment, PaymentProvider, PaymentStatus, User
from bot.services.referral import grant_referral_bonus, get_referral_registered_count, get_referral_paid_count

REFERRAL_BONUS_RUB = Decimal("100.00")


async def test_grant_referral_bonus_credits_referrer_once(db_session):
    referrer = User(telegram_id=600, username="referrer", balance=Decimal("0.00"))
    db_session.add(referrer)
    await db_session.commit()

    invited = User(telegram_id=601, username="invited", referred_by=referrer.id, balance=Decimal("0.00"))
    db_session.add(invited)
    await db_session.commit()

    payment = Payment(
        user_id=invited.id, provider=PaymentProvider.yookassa,
        amount=Decimal("150.00"), status=PaymentStatus.paid,
    )
    db_session.add(payment)
    await db_session.commit()

    await grant_referral_bonus(invited, db_session)

    await db_session.refresh(referrer)
    await db_session.refresh(invited)
    assert referrer.balance == REFERRAL_BONUS_RUB
    assert invited.referral_bonus_granted is True


async def test_grant_referral_bonus_is_not_repeated(db_session):
    referrer = User(telegram_id=602, username="referrer2", balance=Decimal("0.00"))
    db_session.add(referrer)
    await db_session.commit()

    invited = User(
        telegram_id=603, username="invited2", referred_by=referrer.id,
        balance=Decimal("0.00"), referral_bonus_granted=True,
    )
    db_session.add(invited)
    await db_session.commit()

    payment = Payment(
        user_id=invited.id, provider=PaymentProvider.yookassa,
        amount=Decimal("150.00"), status=PaymentStatus.paid,
    )
    db_session.add(payment)
    await db_session.commit()

    await grant_referral_bonus(invited, db_session)

    await db_session.refresh(referrer)
    assert referrer.balance == Decimal("0.00")  # already granted, no second credit


async def test_grant_referral_bonus_skips_non_first_payment(db_session):
    referrer = User(telegram_id=604, username="referrer3", balance=Decimal("0.00"))
    db_session.add(referrer)
    await db_session.commit()

    invited = User(telegram_id=605, username="invited3", referred_by=referrer.id, balance=Decimal("0.00"))
    db_session.add(invited)
    await db_session.commit()

    db_session.add_all([
        Payment(user_id=invited.id, provider=PaymentProvider.yookassa, amount=Decimal("100.00"), status=PaymentStatus.paid),
        Payment(user_id=invited.id, provider=PaymentProvider.yookassa, amount=Decimal("150.00"), status=PaymentStatus.paid),
    ])
    await db_session.commit()

    await grant_referral_bonus(invited, db_session)

    await db_session.refresh(referrer)
    assert referrer.balance == Decimal("0.00")  # this was the 2nd paid payment, not the 1st
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_services/test_referral.py -v`
Expected: FAIL (old `referral.py` has a different `grant_referral_bonus`-shaped API — `ImportError`).

- [ ] **Step 3: Rewrite `bot/services/referral.py`**

```python
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Payment, PaymentStatus, User

REFERRAL_BONUS_RUB = Decimal("100.00")


async def notify_user(telegram_id: int, text: str):
    pass  # reassigned at startup in main.py


async def get_referral_registered_count(user_id: int, session: AsyncSession) -> int:
    result = await session.execute(
        select(func.count(User.id)).where(User.referred_by == user_id)
    )
    return result.scalar_one_or_none() or 0


async def get_referral_paid_count(user_id: int, session: AsyncSession) -> int:
    paid_user_ids = select(Payment.user_id).where(Payment.status == PaymentStatus.paid).distinct()
    result = await session.execute(
        select(func.count(User.id)).where(
            User.referred_by == user_id,
            User.id.in_(paid_user_ids),
        )
    )
    return result.scalar_one_or_none() or 0


async def grant_referral_bonus(user: User, session: AsyncSession) -> None:
    if not user.referred_by or user.referral_bonus_granted:
        return

    paid_count = await session.scalar(
        select(func.count(Payment.id)).where(
            Payment.user_id == user.id,
            Payment.status == PaymentStatus.paid,
        )
    )
    if (paid_count or 0) != 1:
        return  # not the user's first paid payment

    referrer = await session.get(User, user.referred_by)
    if referrer is None:
        return

    referrer.balance += REFERRAL_BONUS_RUB
    user.referral_bonus_granted = True
    await session.commit()
    await notify_user(referrer.telegram_id, f"⚡ +{REFERRAL_BONUS_RUB} ₽ на баланс за приглашённого друга!")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_services/test_referral.py -v`
Expected: PASS.

- [ ] **Step 5: Wire `credit_topup` (Task 5) to call `grant_referral_bonus` now that `referral.py` is safe to import**

In `bot/services/balance.py`, add the import and the call:

```python
from bot.services.remnawave import remnawave
from bot.services.referral import grant_referral_bonus
```

At the end of `credit_topup`, after the existing `notify_user(...)` line:

```python
    await grant_referral_bonus(user, session)
```

- [ ] **Step 6: Write the integration test proving the wire-up**

```python
# tests/test_services/test_balance.py (append)
async def test_credit_topup_grants_referral_bonus_on_first_payment(db_session):
    from bot.services.balance import credit_topup

    referrer = User(telegram_id=510, username="ref", balance=Decimal("0.00"))
    db_session.add(referrer)
    await db_session.commit()

    invited = User(telegram_id=511, username="invited", referred_by=referrer.id, balance=Decimal("0.00"))
    db_session.add(invited)
    await db_session.commit()

    payment = Payment(user_id=invited.id, provider=PaymentProvider.yookassa, amount=Decimal("150.00"))
    db_session.add(payment)
    await db_session.commit()

    await credit_topup(payment.id, Decimal("150.00"), "yk_ext_ref", db_session)

    await db_session.refresh(referrer)
    assert referrer.balance == Decimal("100.00")
```

- [ ] **Step 7: Run the full suite**

Run: `pytest -q`
Expected: all green.

- [ ] **Step 8: Commit**

```bash
git add bot/services/referral.py bot/services/balance.py tests/test_services/test_referral.py tests/test_services/test_balance.py
git commit -m "feat: replace referral withdrawal system with flat one-time balance bonus"
```

---

### Task 9: Scheduler — daily billing job

**Files:**
- Rewrite: `bot/scheduler/tasks.py`
- Test: `tests/test_scheduler.py`

**Interfaces:**
- Produces: `run_daily_billing() -> None`.
- Consumes: `bot.services.balance.get_daily_rate_per_device/calculate_daily_charge` (Task 5), `bot.services.remnawave.remnawave.disable_user` (unchanged).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_scheduler.py
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from bot.database.models import AppSettings, User
import bot.scheduler.tasks as tasks


def _mock_bot():
    bot = AsyncMock()
    return bot


async def test_daily_billing_deducts_balance_for_active_users(db_session):
    db_session.add(AppSettings(id=1, daily_rate_per_device=Decimal("1.00")))
    user = User(telegram_id=700, username="u1", balance=Decimal("10.00"), devices_limit=1, access_active=True)
    db_session.add(user)
    await db_session.commit()

    bot = _mock_bot()
    with patch.object(tasks, "_get_bot", AsyncMock(return_value=bot)), \
         patch.object(tasks, "AsyncSessionLocal", lambda: db_session):
        await tasks.run_daily_billing()

    await db_session.refresh(user)
    assert user.balance == Decimal("9.00")


async def test_daily_billing_warns_one_day_before_zero(db_session):
    db_session.add(AppSettings(id=1, daily_rate_per_device=Decimal("1.00")))
    user = User(telegram_id=701, username="u2", balance=Decimal("1.00"), devices_limit=1, access_active=True)
    db_session.add(user)
    await db_session.commit()

    bot = _mock_bot()
    with patch.object(tasks, "_get_bot", AsyncMock(return_value=bot)), \
         patch.object(tasks, "AsyncSessionLocal", lambda: db_session):
        await tasks.run_daily_billing()

    await db_session.refresh(user)
    assert user.balance == Decimal("0.00")
    assert user.grace_started_at is not None
    assert bot.send_message.await_count == 1


async def test_daily_billing_disables_access_after_grace_expires(db_session):
    db_session.add(AppSettings(id=1, daily_rate_per_device=Decimal("1.00")))
    user = User(
        telegram_id=702, username="u3", balance=Decimal("0.00"), devices_limit=1,
        access_active=True, grace_started_at=datetime.now(timezone.utc) - timedelta(hours=25),
        remnawave_uuid="uuid-702",
    )
    db_session.add(user)
    await db_session.commit()

    bot = _mock_bot()
    with patch.object(tasks, "_get_bot", AsyncMock(return_value=bot)), \
         patch.object(tasks, "AsyncSessionLocal", lambda: db_session), \
         patch.object(tasks, "remnawave") as mock_remnawave:
        mock_remnawave.disable_user = AsyncMock()
        await tasks.run_daily_billing()
        mock_remnawave.disable_user.assert_called_once_with("uuid-702")

    await db_session.refresh(user)
    assert user.access_active is False


async def test_daily_billing_skips_inactive_users(db_session):
    db_session.add(AppSettings(id=1, daily_rate_per_device=Decimal("1.00")))
    user = User(telegram_id=703, username="u4", balance=Decimal("5.00"), devices_limit=1, access_active=False)
    db_session.add(user)
    await db_session.commit()

    bot = _mock_bot()
    with patch.object(tasks, "_get_bot", AsyncMock(return_value=bot)), \
         patch.object(tasks, "AsyncSessionLocal", lambda: db_session):
        await tasks.run_daily_billing()

    await db_session.refresh(user)
    assert user.balance == Decimal("5.00")  # untouched, access already inactive
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_scheduler.py -v`
Expected: FAIL (`AttributeError: module 'bot.scheduler.tasks' has no attribute 'run_daily_billing'`).

- [ ] **Step 3: Rewrite `bot/scheduler/tasks.py`**

```python
from datetime import datetime, timezone, timedelta

from sqlalchemy import select

from bot.database.models import User
from bot.database.session import AsyncSessionLocal
from bot.services.balance import get_daily_rate_per_device, calculate_daily_charge
from bot.services.remnawave import remnawave

GRACE_PERIOD = timedelta(hours=24)


async def _get_bot():
    from bot.main import _bot_instance
    return _bot_instance


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def run_daily_billing():
    async with AsyncSessionLocal() as session:
        bot = await _get_bot()
        now = datetime.now(timezone.utc)
        daily_rate = await get_daily_rate_per_device(session)

        result = await session.execute(select(User).where(User.access_active == True))
        users = result.scalars().all()

        for user in users:
            charge = calculate_daily_charge(daily_rate, user.devices_limit)
            user.balance -= charge

            if 0 < user.balance <= charge:
                try:
                    await bot.send_message(
                        user.telegram_id,
                        "⚡ Баланс скоро закончится, пополните — /start",
                    )
                except Exception:
                    pass

            if user.balance <= 0:
                if user.grace_started_at is None:
                    user.grace_started_at = now
                    try:
                        await bot.send_message(
                            user.telegram_id,
                            "⚡ Баланс исчерпан. 24 часа на пополнение, иначе доступ будет отключён.",
                        )
                    except Exception:
                        pass
                elif now - _aware(user.grace_started_at) >= GRACE_PERIOD:
                    user.access_active = False
                    if user.remnawave_uuid:
                        try:
                            await remnawave.disable_user(user.remnawave_uuid)
                        except Exception:
                            pass
                    try:
                        await bot.send_message(
                            user.telegram_id,
                            "❌ Доступ к Zeus VPN отключён. Пополните баланс — /start",
                        )
                    except Exception:
                        pass

        await session.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_scheduler.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bot/scheduler/tasks.py tests/test_scheduler.py
git commit -m "feat: replace expiry-based scheduler jobs with daily balance billing"
```

---

### Task 10: Registration and main menu — balance-aware, rebranded

**Files:**
- Modify: `bot/handlers/start.py`
- Test: `tests/test_handlers/test_start.py`

**Interfaces:**
- Produces: `build_menu_text(user: User) -> str` (signature changes — no longer takes `sub`).
- Consumes: `bot.services.remnawave.remnawave.create_user()` (unchanged).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_handlers/test_start.py
from decimal import Decimal
from bot.database.models import User
from bot.handlers.start import build_menu_text


def test_build_menu_text_shows_balance_and_devices():
    user = User(telegram_id=1, balance=Decimal("42.50"), devices_limit=2, access_active=True)
    text = build_menu_text(user)
    assert "Zeus VPN" in text
    assert "42.5" in text or "42.50" in text
    assert "2" in text


def test_build_menu_text_shows_disabled_access():
    user = User(telegram_id=1, balance=Decimal("0.00"), devices_limit=1, access_active=False)
    text = build_menu_text(user)
    assert "отключ" in text.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_handlers/test_start.py -v`
Expected: FAIL (`TypeError: build_menu_text() missing 1 required positional argument: 'sub'` or brand text mismatch).

- [ ] **Step 3: Rewrite the relevant parts of `bot/handlers/start.py`**

Replace `build_menu_text` and the body of `start_handler` from `if not user.terms_accepted:` onward:

```python
def build_menu_text(user: User) -> str:
    if user.access_active:
        status_lines = (
            f"✅ Доступ: <b>Активен</b>\n"
            f"💰 Баланс: <b>{user.balance} ₽</b>\n"
            f"📱 Устройств: {user.devices_limit}"
        )
    else:
        status_lines = (
            f"❌ Доступ: <b>Отключён</b> (баланс исчерпан)\n"
            f"💰 Баланс: <b>{user.balance} ₽</b>"
        )

    return (
        f"⚡️ <b>ZEUS VPN</b>\n\n"
        f"🆔 ID: <code>{user.telegram_id}</code>\n\n"
        f"{status_lines}\n\n"
        f"Выберите раздел:"
    )
```

In `start_handler`, replace the block that creates a new `User` and everything from `if not user.terms_accepted:` to the end of the subscription lookup with:

```python
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            telegram_id=telegram_id,
            username=username,
            referred_by=referred_by_id,
            balance=Decimal("1.00"),
            devices_limit=1,
        )
        session.add(user)
        await session.commit()
    elif referred_by_id and referred_by_id != user.referred_by:
        await message.answer(
            "❌ <b>Бонус не получен</b>\n\n"
            "Вы уже зарегистрированы в Zeus VPN.\n"
            "Реферальный бонус начисляется только при первой регистрации.",
            parse_mode="HTML",
        )

    if not user.terms_accepted:
        from bot.handlers.about import get_terms_accept_text
        await message.answer(
            get_terms_accept_text(),
            reply_markup=terms_accept_keyboard(),
            parse_mode="HTML",
        )
        return

    text = build_menu_text(user)
    keyboard = main_menu_keyboard(has_access=user.access_active)
```

Add `from decimal import Decimal` to the imports, and update the two `message.answer_photo(...)`/`message.answer(...)` calls further down to use the new `text`/`keyboard` variables (unchanged otherwise — they already reference `text`/`keyboard` by name).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_handlers/test_start.py -v`
Expected: PASS (after Task 11 lands `main_menu_keyboard(has_access=...)` — if run standalone, temporarily accept the old `has_sub` kwarg name too; Task 11 finalizes it).

- [ ] **Step 5: Commit**

```bash
git add bot/handlers/start.py tests/test_handlers/test_start.py
git commit -m "feat: rebrand registration and main menu to balance model"
```

---

### Task 11: Keyboards and menu — top-up/devices UI, drop plan UI

**Files:**
- Modify: `bot/keyboards/inline.py`
- Modify: `bot/handlers/menu.py`
- Delete: `bot/handlers/subscription.py`, `bot/handlers/promo.py`'s order-related callbacks (handled in Task 14)

**Interfaces:**
- Produces: `main_menu_keyboard(has_access: bool) -> InlineKeyboardMarkup`, `topup_amount_prompt_keyboard() -> InlineKeyboardMarkup`, `devices_count_keyboard(current: int) -> InlineKeyboardMarkup`, `payment_formed_keyboard(pay_url: str)` (unchanged, kept).
- Removes: `PRICE_TABLE`, `DEVICE_OPTIONS`, `get_price`, `plans_keyboard`, `devices_select_keyboard`, `order_confirm_keyboard`, `upgrade_devices_keyboard`, `connect_vpn_keyboard(has_sub=...)` → `connect_vpn_keyboard(has_access=...)`.

- [ ] **Step 1: Rewrite `bot/keyboards/inline.py`**

```python
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
        [InlineKeyboardButton(text="📱 Мои устройства", callback_data="my_devices")],
        [InlineKeyboardButton(text="🔢 Число устройств", callback_data="change_devices")],
        [InlineKeyboardButton(text="📖 Инструкция", callback_data="instruction")],
        [InlineKeyboardButton(text="👥 Пригласить друзей", callback_data="referrals")],
        [InlineKeyboardButton(text="ℹ️ О сервисе", callback_data="about")],
        [InlineKeyboardButton(text="🆘 Поддержка", callback_data="support")],
    ])


def connect_vpn_keyboard(has_access: bool) -> InlineKeyboardMarkup:
    if has_access:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="topup", style=P)],
            [InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_menu")],
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="topup", style=P)],
        [InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_menu")],
    ])


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_menu")]
    ])


def referral_keyboard(ref_link: str) -> InlineKeyboardMarkup:
    share_url = f"https://t.me/share/url?url={ref_link}&text=Попробуй%20Zeus%20VPN%20—%20стабильный%20VPN"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Поделиться ссылкой", url=share_url, style=P)],
        [InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_menu")],
    ])


def support_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Написать в поддержку", url="https://t.me/zeus_vpnsupport", style=P)],
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


def topup_amount_prompt_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Отмена", callback_data="back_to_menu")],
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
        buttons.append([InlineKeyboardButton(text=f"{mark}{n} устр", callback_data=f"set_devices:{n}")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
```

- [ ] **Step 2: Rewrite `bot/handlers/menu.py`**

```python
from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import User
from bot.handlers.start import build_menu_text
from bot.keyboards.inline import (
    back_to_menu_keyboard,
    connect_vpn_keyboard,
    main_menu_keyboard,
    support_keyboard,
)
from bot.services.remnawave import remnawave
from bot.utils import send_section, smart_edit

router = Router()


@router.callback_query(F.data == "connect_vpn")
async def connect_vpn_handler(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))

    if user and user.access_active:
        sub_url = ""
        try:
            sub_url = await remnawave.get_subscription_url(f"user_{user.telegram_id}")
        except Exception:
            pass

        if sub_url:
            text = (
                "⚡️ <b>ПОДКЛЮЧИТЬ VPN</b>\n\n"
                f"💰 Баланс: <b>{user.balance} ₽</b>\n"
                f"📱 Устройств: <b>{user.devices_limit}</b>\n\n"
                "📋 <b>Ссылка подписки:</b>\n"
                f"<code>{sub_url}</code>\n\n"
                "Скопируй ссылку и вставь в:\n"
                "• <b>Hiddify</b> (рекомендуем)\n"
                "• <b>v2rayNG</b> / <b>Happ</b>"
            )
        else:
            text = (
                "⚡️ <b>ПОДКЛЮЧИТЬ VPN</b>\n\n"
                f"💰 Баланс: <b>{user.balance} ₽</b>\n\n"
                "⚠️ Не удалось загрузить ссылку подписки.\n"
                "Попробуй позже или обратись в поддержку."
            )
    else:
        text = (
            "⚡️ <b>ПОДКЛЮЧИТЬ VPN</b>\n\n"
            "❌ Доступ отключён — баланс исчерпан.\n\n"
            "Пополни баланс, чтобы получить доступ к Zeus VPN."
        )

    await smart_edit(callback, text, connect_vpn_keyboard(has_access=bool(user and user.access_active)))


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))

    if not user or not user.terms_accepted:
        from bot.handlers.about import get_terms_accept_text
        from bot.keyboards.inline import terms_accept_keyboard
        await smart_edit(callback, get_terms_accept_text(), terms_accept_keyboard())
        return

    await send_section(
        callback,
        "main",
        build_menu_text(user),
        main_menu_keyboard(has_access=user.access_active),
    )


@router.callback_query(F.data == "support")
async def support(callback: CallbackQuery):
    await callback.answer()
    await send_section(
        callback,
        "support",
        "🆘 <b>Поддержка Zeus VPN</b>\n\n"
        "Возникли вопросы или проблемы с подключением?\n"
        "Напиши нам — поможем разобраться.\n\n"
        "⏱ Время ответа: до 24 часов.",
        support_keyboard(),
    )
```

(`add_devices` callback is dropped entirely — Task 12 replaces it with the `change_devices`/`set_devices:{n}` flow.)

- [ ] **Step 3: Delete the plan-picker handler**

```bash
git rm bot/handlers/subscription.py
```

- [ ] **Step 4: Run the full suite**

Run: `pytest -q`
Expected: failures only in files not yet updated (`bot/handlers/devices.py`, `bot/handlers/admin.py`, `bot/handlers/payment.py`, `bot/main.py` still import removed symbols) — confirm the failures are import errors in those specific files, nothing in `tests/test_services/` or `tests/test_webhooks/`.

- [ ] **Step 5: Commit**

```bash
git add bot/keyboards/inline.py bot/handlers/menu.py
git rm bot/handlers/subscription.py
git commit -m "feat: rebuild menu/keyboards around balance model, drop plan picker"
```

---

### Task 12: Top-up and device-count handlers

**Files:**
- Rewrite: `bot/handlers/payment.py`
- Test: `tests/test_handlers/test_payment.py`

**Interfaces:**
- Consumes: `bot.services.yookassa.create_payment()` (Task 6), `bot.keyboards.inline.topup_amount_prompt_keyboard/payment_formed_keyboard/devices_count_keyboard` (Task 11).
- Produces callback routes: `topup`, `change_devices`, `set_devices:{n}`; FSM state `PaymentStates.waiting_for_amount`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_handlers/test_payment.py
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from bot.database.models import Payment, PaymentProvider, PaymentStatus, User
from bot.handlers.payment import _validate_topup_amount, MIN_TOPUP_MESSAGE


def test_validate_topup_amount_rejects_below_minimum():
    ok, error = _validate_topup_amount(50.0, min_amount=100.0)
    assert ok is False
    assert error == MIN_TOPUP_MESSAGE


def test_validate_topup_amount_accepts_minimum_and_above():
    ok, error = _validate_topup_amount(100.0, min_amount=100.0)
    assert ok is True
    assert error is None

    ok, error = _validate_topup_amount(250.0, min_amount=100.0)
    assert ok is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_handlers/test_payment.py -v`
Expected: FAIL (`ModuleNotFoundError` — old `payment.py` doesn't define `_validate_topup_amount`).

- [ ] **Step 3: Write `bot/handlers/payment.py`**

```python
from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_settings
from bot.database.models import Payment, PaymentProvider, User
from bot.keyboards.inline import (
    back_to_menu_keyboard,
    devices_count_keyboard,
    main_menu_keyboard,
    payment_formed_keyboard,
    topup_amount_prompt_keyboard,
)
from bot.services.yookassa import create_payment
from bot.utils import smart_edit

router = Router()

MIN_TOPUP_MESSAGE = "⚡ Минимальная сумма пополнения — {min_amount:.0f} ₽"
PROVIDER_UNAVAILABLE_MESSAGE = "⚡ Пополнение баланса скоро откроется"


class PaymentStates(StatesGroup):
    waiting_for_amount = State()


def _validate_topup_amount(amount: float, min_amount: float) -> tuple[bool, str | None]:
    if amount < min_amount:
        return False, MIN_TOPUP_MESSAGE.format(min_amount=min_amount)
    return True, None


@router.callback_query(F.data == "topup")
async def topup_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    s = get_settings()
    if not s.YOOKASSA_SHOP_ID or not s.YOOKASSA_SECRET_KEY:
        await smart_edit(callback, PROVIDER_UNAVAILABLE_MESSAGE, back_to_menu_keyboard())
        return
    await state.set_state(PaymentStates.waiting_for_amount)
    await smart_edit(
        callback,
        f"💰 <b>ПОПОЛНЕНИЕ БАЛАНСА</b>\n\nВведите сумму (минимум {s.MIN_TOPUP_RUB:.0f} ₽):",
        topup_amount_prompt_keyboard(),
    )


@router.message(PaymentStates.waiting_for_amount)
async def topup_amount_input(message: Message, session: AsyncSession, state: FSMContext):
    await state.clear()
    s = get_settings()

    try:
        amount = float(message.text.strip().replace(",", "."))
    except ValueError:
        await message.answer("❌ Введите число, например: 200", reply_markup=back_to_menu_keyboard())
        return

    ok, error = _validate_topup_amount(amount, s.MIN_TOPUP_RUB)
    if not ok:
        await message.answer(error, reply_markup=back_to_menu_keyboard())
        return

    user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))

    payment = Payment(user_id=user.id, provider=PaymentProvider.yookassa, amount=Decimal(str(amount)))
    session.add(payment)
    await session.flush()
    await session.commit()

    pay_url = await create_payment(amount, payment.id, "Пополнение баланса Zeus VPN")

    await message.answer(
        f"💰 <b>ПЛАТЁЖ СФОРМИРОВАН</b>\n\n└ 💲 Сумма: {amount:.0f} ₽\n\nНажмите кнопку ниже для оплаты.",
        reply_markup=payment_formed_keyboard(pay_url),
    )


@router.callback_query(F.data == "change_devices")
async def change_devices_start(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
    await smart_edit(
        callback,
        f"🔢 <b>ЧИСЛО УСТРОЙСТВ</b>\n\nСейчас: {user.devices_limit}. Выберите новое значение — влияет на суточное списание:",
        devices_count_keyboard(user.devices_limit),
    )


@router.callback_query(F.data.startswith("set_devices:"))
async def set_devices(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    new_limit = int(callback.data.split(":")[1])
    user = await session.scalar(select(User).where(User.telegram_id == callback.from_user.id))
    user.devices_limit = new_limit
    await session.commit()
    await smart_edit(
        callback,
        f"✅ Число устройств обновлено: <b>{new_limit}</b>",
        main_menu_keyboard(has_access=user.access_active),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_handlers/test_payment.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bot/handlers/payment.py tests/test_handlers/test_payment.py
git commit -m "feat: rewrite payment handler for balance top-up and device-count changes"
```

---

### Task 13: Devices list handler — read from `User` instead of `Subscription`

**Files:**
- Modify: `bot/handlers/devices.py`

**Interfaces:**
- Consumes: `User.devices_limit`, `User.access_active` (Task 3).

- [ ] **Step 1: Edit `my_devices`**

Replace the subscription lookup and the `if not sub:` gate:

```python
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
```

Below that, replace every `limit = sub.devices_limit` with `limit = user.devices_limit`, and delete the now-unused `sub` lookup lines (`Subscription`/`SubscriptionStatus` import and the `select(Subscription)...` block are gone since `sub` is no longer used anywhere in this file).

Update `_no_sub_keyboard()`:

```python
def _no_sub_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="topup")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")],
    ])
```

Remove the `from bot.database.models import Subscription, SubscriptionStatus, User` import line and replace with `from bot.database.models import User`.

- [ ] **Step 2: Run the full suite**

Run: `pytest -q`
Expected: remaining failures confined to `bot/handlers/admin.py`, `bot/handlers/promo.py`, `bot/main.py`, `bot/handlers/referral.py`, `bot/handlers/about.py` (still pending tasks).

- [ ] **Step 3: Commit**

```bash
git add bot/handlers/devices.py
git commit -m "feat: adapt devices handler to User-based access fields"
```

---

### Task 14: Referral handler — balance-based stats, no withdrawal

**Files:**
- Modify: `bot/handlers/referral.py`

**Interfaces:**
- Consumes: `get_referral_registered_count/get_referral_paid_count` (Task 8, unchanged signatures).

- [ ] **Step 1: Rewrite `bot/handlers/referral.py`**

```python
from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import User
from bot.keyboards.inline import referral_keyboard
from bot.services.referral import get_referral_registered_count, get_referral_paid_count, REFERRAL_BONUS_RUB
from bot.utils import smart_edit

router = Router()


@router.callback_query(F.data == "referrals")
async def referrals_menu(callback: CallbackQuery, session: AsyncSession):
    await callback.answer()
    result = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))
    user = result.scalar_one()
    registered = await get_referral_registered_count(user.id, session)
    paid = await get_referral_paid_count(user.id, session)
    me = await callback.bot.get_me()
    ref_link = f"https://t.me/{me.username}?start=ref{callback.from_user.id}"

    await smart_edit(
        callback,
        f"🎁 <b>РЕФЕРАЛЬНАЯ ПРОГРАММА ZEUS VPN</b>\n\n"
        f"Приглашайте друзей и получайте бонус на баланс!\n\n"
        f"🔗 <b>ВАША ССЫЛКА:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"📊 <b>СТАТИСТИКА:</b>\n"
        f"┣ ✅ Регистраций: <b>{registered}</b>\n"
        f"┗ 💳 Оплатили: <b>{paid}</b>\n\n"
        f"💡 <b>КАК ЭТО РАБОТАЕТ:</b>\n"
        f"1️⃣ Отправьте вашу ссылку другу\n"
        f"2️⃣ Друг регистрируется и пополняет баланс\n"
        f"3️⃣ Вам начисляется <b>+{REFERRAL_BONUS_RUB:.0f} ₽</b> на баланс\n\n"
        f"<i>Бонус начисляется один раз, за первое пополнение друга</i>",
        referral_keyboard(ref_link),
    )
```

- [ ] **Step 2: Run the full suite**

Run: `pytest -q`
Expected: remaining failures confined to `admin.py`, `promo.py`, `about.py`, `main.py`.

- [ ] **Step 3: Commit**

```bash
git add bot/handlers/referral.py
git commit -m "feat: rewrite referral menu for flat balance bonus"
```

---

### Task 15: Admin panel — drop Plan/Subscription flows, add rate control

**Files:**
- Modify: `bot/handlers/admin.py`
- Modify: `bot/keyboards/admin.py`
- Test: `tests/test_handlers/test_admin_rate.py`

**Interfaces:**
- Produces: `/setrate <value>` command (or `adm_set_rate` FSM flow) that calls `bot.services.balance.set_daily_rate_per_device()` (Task 5).
- Removes: `adm_give_sub:`/`AdminStates.give_sub_days`, `adm_subs:` (active subscriptions list), `admin_subs_keyboard`, `admin_plans_keyboard`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_handlers/test_admin_rate.py
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from bot.database.models import User
from bot.handlers.admin import adm_set_rate_input, AdminStates


async def test_adm_set_rate_input_updates_rate(db_session):
    admin = User(telegram_id=999, username="root", is_admin=True)
    db_session.add(admin)
    await db_session.commit()

    message = MagicMock()
    message.from_user.id = 999
    message.text = "2.50"
    message.answer = AsyncMock()

    state = AsyncMock()
    state.get_data = AsyncMock(return_value={})

    await adm_set_rate_input(message, db_session, state)

    from bot.services.balance import get_daily_rate_per_device
    rate = await get_daily_rate_per_device(db_session)
    assert rate == Decimal("2.50")
    message.answer.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_handlers/test_admin_rate.py -v`
Expected: FAIL (`ImportError: cannot import name 'adm_set_rate_input'`).

- [ ] **Step 3: Edit `bot/handlers/admin.py`**

Remove the imports `Payment... Plan, Subscription, SubscriptionStatus` in favor of just what's still used, and delete these blocks entirely: `adm_give_sub`, `_adm_give_sub_days_impl`/`adm_give_sub_days` and the `give_sub_days` state, `adm_subs`. Update the remaining imports to:

```python
from bot.database.models import Payment, PaymentStatus, User, VpnServer
```

Update `AdminStates` — remove `give_sub_days`, add `set_rate`:

```python
class AdminStates(StatesGroup):
    search_user = State()
    broadcast_text = State()
    new_promo_input = State()
    edit_instruction = State()
    set_rate = State()
    add_server = State()
    set_photo = State()
```

Replace `adm_stats` (it referenced `Subscription`/`SubscriptionStatus`) with:

```python
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
```

Update `_show_user` (dropped the `Subscription` lookup/`sub_line`, `bonus_days` field):

```python
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
```

Add the rate-setting flow (near the promo-code section):

```python
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
```

- [ ] **Step 4: Edit `bot/keyboards/admin.py`**

In `admin_main_keyboard`, replace the `"💳 Подписки"` button with a rate-setting button, and delete `admin_plans_keyboard`/`admin_subs_keyboard` entirely:

```python
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
```

In `admin_user_keyboard`, replace `"📅 Добавить / убрать дни"` (`adm_give_sub:`) — that callback no longer exists — with nothing extra (ban/unban only):

```python
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
```

Delete `admin_plans_keyboard` and `admin_subs_keyboard` from the file.

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_handlers/test_admin_rate.py -v`
Expected: PASS.

- [ ] **Step 6: Run the full suite**

Run: `pytest -q`
Expected: remaining failures confined to `promo.py`, `about.py`, `main.py`.

- [ ] **Step 7: Commit**

```bash
git add bot/handlers/admin.py bot/keyboards/admin.py tests/test_handlers/test_admin_rate.py
git commit -m "feat: replace admin subscription tools with daily-rate control"
```

---

### Task 16: Promo codes — credit balance instead of discounting an order

**Files:**
- Modify: `bot/handlers/promo.py`
- Test: `tests/test_handlers/test_promo.py`

**Interfaces:**
- Consumes: `bot.services.promo.validate_promo/record_usage` (unchanged).
- Removes: `promo_apply_order:`/`promo_cancel_order:` callbacks and the `order_confirm_keyboard`/`get_price`/`Plan` dependency (that flow no longer exists after Task 11).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_handlers/test_promo.py
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from bot.database.models import PromoCode, User
from bot.handlers.promo import redeem_promo_code


async def test_redeem_promo_code_credits_balance(db_session):
    user = User(telegram_id=800, username="promouser", balance=Decimal("0.00"))
    promo = PromoCode(code="ZEUS50", amount=50)
    db_session.add_all([user, promo])
    await db_session.commit()

    message = MagicMock()
    message.from_user.id = 800
    message.text = "ZEUS50"
    message.answer = AsyncMock()

    await redeem_promo_code(message, db_session)

    await db_session.refresh(user)
    assert user.balance == Decimal("50.00")
    message.answer.assert_called_once()


async def test_redeem_promo_code_rejects_reuse(db_session):
    user = User(telegram_id=801, username="promouser2", balance=Decimal("0.00"))
    promo = PromoCode(code="ONESHOT", amount=30)
    db_session.add_all([user, promo])
    await db_session.commit()

    message = MagicMock()
    message.from_user.id = 801
    message.text = "ONESHOT"
    message.answer = AsyncMock()

    await redeem_promo_code(message, db_session)
    await db_session.refresh(user)
    assert user.balance == Decimal("30.00")

    message2 = MagicMock()
    message2.from_user.id = 801
    message2.text = "ONESHOT"
    message2.answer = AsyncMock()
    await redeem_promo_code(message2, db_session)

    await db_session.refresh(user)
    assert user.balance == Decimal("30.00")  # unchanged — already used
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_handlers/test_promo.py -v`
Expected: FAIL (`ImportError: cannot import name 'redeem_promo_code'`).

- [ ] **Step 3: Rewrite `bot/handlers/promo.py`**

Keep the admin commands (`cmd_new_promo`, `cmd_list_promos`, `cmd_delete_promo`) exactly as-is — they're unaffected by the billing model change. Replace everything from `class PromoStates` down to the end of the file with:

```python
class PromoStates(StatesGroup):
    waiting_for_code = State()


@router.message(Command("promo"))
async def cmd_promo_prompt(message: Message, state: FSMContext):
    await state.set_state(PromoStates.waiting_for_code)
    await message.answer("🏷 Введи промокод:")


@router.message(PromoStates.waiting_for_code)
async def promo_code_input(message: Message, session: AsyncSession, state: FSMContext):
    await state.clear()
    await redeem_promo_code(message, session)


async def redeem_promo_code(message: Message, session: AsyncSession) -> None:
    user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
    promo, error = await validate_promo(session, message.text.strip(), user.id)

    if error:
        await message.answer(error)
        return

    from decimal import Decimal
    user.balance += Decimal(promo.amount)
    await record_usage(session, promo.id, user.id)
    await session.commit()

    await message.answer(
        f"✅ Промокод <b>{promo.code}</b> применён! На баланс зачислено <b>{promo.amount} ₽</b>.\n"
        f"Текущий баланс: <b>{user.balance} ₽</b>",
        parse_mode="HTML",
    )
```

Drop the `order_confirm_keyboard`/`get_price`/`Plan` import line — replace it with just what's still needed:

```python
from bot.database.models import User
from bot.services.promo import validate_promo, record_usage
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_handlers/test_promo.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bot/handlers/promo.py tests/test_handlers/test_promo.py
git commit -m "feat: repoint promo codes to credit balance directly"
```

---

### Task 17: `main.py` wiring — init, scheduler, brand

**Files:**
- Modify: `bot/main.py`

**Interfaces:**
- Consumes: `bot.scheduler.tasks.run_daily_billing` (Task 9), `bot.services.balance.notify_user`/`bot.services.referral.notify_user` (Task 5/8).

- [ ] **Step 1: Rewrite `_init_db`**

```python
async def _init_db():
    from bot.database.session import engine
    from bot.database.models import Base, AppSettings
    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from bot.database.session import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        existing = await session.get(AppSettings, 1)
        if existing is None:
            session.add(AppSettings(id=1, daily_rate_per_device=1.00))
            await session.commit()
```

(The old SQLite `ALTER TABLE`/`Plan` seeding hacks are gone — this is a fresh schema with an Alembic migration as the real source of truth for Postgres; `_init_db` only handles first-run SQLite dev convenience.)

- [ ] **Step 2: Update `main()`**

Replace the `sub_service.notify_user = _notify` block:

```python
    from bot.services import balance as balance_service
    from bot.services import referral as referral_service

    async def _notify(telegram_id: int, text: str):
        try:
            await bot.send_message(telegram_id, text, parse_mode="HTML")
        except Exception:
            pass

    balance_service.notify_user = _notify
    referral_service.notify_user = _notify
```

Update the router includes — remove `subscription`:

```python
    from bot.handlers import about, admin, devices, fallback, instruction, menu, payment, promo, referral, start

    dp.include_router(about.router)
    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(instruction.router)
    dp.include_router(menu.router)
    dp.include_router(devices.router)
    dp.include_router(payment.router)
    dp.include_router(referral.router)
    dp.include_router(promo.router)
    dp.include_router(fallback.router)  # must be last
```

Replace the scheduler block:

```python
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from bot.scheduler.tasks import run_daily_billing

    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(run_daily_billing, "cron", hour=0, minute=0)
    scheduler.start()
```

Update the bot-commands/admin-commands text: `"Главное меню DS-VPN"` → `"Главное меню Zeus VPN"` (both occurrences).

- [ ] **Step 3: Generalize the SSL cert paths (they hardcode the old domain)**

Add to `bot/config.py` (Task 2's `Settings`, revisit now):

```python
    SSL_CERT_PATH: str = ""
    SSL_KEY_PATH: str = ""
```

Add to `.env.example`: `SSL_CERT_PATH=` / `SSL_KEY_PATH=`.

In `main()`, replace the hardcoded `uvicorn.Config(...)` block:

```python
    import uvicorn
    from bot.webhooks.app import create_app

    webhook_app = create_app()
    uvicorn_kwargs = dict(host="0.0.0.0", port=8443, log_level="info")
    if s.SSL_CERT_PATH and s.SSL_KEY_PATH:
        uvicorn_kwargs["ssl_certfile"] = s.SSL_CERT_PATH
        uvicorn_kwargs["ssl_keyfile"] = s.SSL_KEY_PATH
    config = uvicorn.Config(webhook_app, **uvicorn_kwargs)
```

- [ ] **Step 4: Run the full suite**

Run: `pytest -q`
Expected: all green — this is the first point where every module imports cleanly again.

- [ ] **Step 5: Commit**

```bash
git add bot/main.py bot/config.py .env.example
git commit -m "feat: wire daily billing scheduler and generalize deployment config"
```

---

### Task 18: Branding sweep — legal texts and remaining strings

**Files:**
- Modify: `bot/handlers/about.py`

**Interfaces:** none (content-only).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_handlers/test_about.py
from bot.handlers.about import _PRIVACY, _TERMS, _TERMS_ACCEPT_TEXT


def test_legal_texts_use_new_brand_and_provider():
    for text in (_PRIVACY, _TERMS, _TERMS_ACCEPT_TEXT):
        assert "DS-VPN" not in text
        assert "Zeus VPN" in text
    assert "FreeKassa" not in _PRIVACY
    assert "CryptoBot" not in _PRIVACY
    assert "ЮKassa" in _PRIVACY
    assert "@ds_vpnsupport" not in _PRIVACY
    assert "@zeus_vpnsupport" in _PRIVACY
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_handlers/test_about.py -v`
Expected: FAIL (old text still says `DS-VPN`, `FreeKassa`, `CryptoBot`, `@ds_vpnsupport`).

- [ ] **Step 3: Edit `bot/handlers/about.py`**

Global find/replace across `_PRIVACY`, `_TERMS`, `_TERMS_ACCEPT_TEXT`, and the `about_handler`/`about_support_handler` inline strings:
- `DS-VPN` → `Zeus VPN`
- `@ds_vpnsupport` → `@zeus_vpnsupport`
- In `_PRIVACY`'s "Передача третьим лицам" clause: `платёжными операторами (FreeKassa, CryptoBot)` → `платёжным оператором (ЮKassa)`

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_handlers/test_about.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bot/handlers/about.py tests/test_handlers/test_about.py
git commit -m "feat: finish brand sweep of legal and support text"
```

---

### Task 19: Final sweep and verification

**Files:** none created — grep + full-suite verification only.

- [ ] **Step 1: Grep for any remaining legacy references**

Run each and confirm zero matches (excluding `docs/superpowers/`):

```bash
grep -rn "DS-VPN" bot/
grep -rn "ds_vpnsupport" bot/
grep -rn "FreeKassa\|CryptoBot\|Lava" bot/
grep -rn "\bPlan\b\|\bSubscription\b" bot/ | grep -v "PromoCode\|VpnServer"
```

Fix any stragglers found (most likely candidates: leftover `SubscriptionStatus` imports in files not touched by this plan, e.g. `bot/handlers/instruction.py` or `bot/handlers/fallback.py` — check both).

- [ ] **Step 2: Run the full test suite one last time**

Run: `pytest -q`
Expected: 100% pass, no warnings about unused imports/undefined names.

- [ ] **Step 3: Manual smoke check of `.env.example` completeness**

Confirm every `Settings` field in `bot/config.py` has a corresponding line in `.env.example` (diff by eye — small file, no tooling needed).

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: final branding and legacy-reference sweep"
```

- [ ] **Step 5: Tag the milestone**

```bash
git tag v0.1.0-balance-model
```
