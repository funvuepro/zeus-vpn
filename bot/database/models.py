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
