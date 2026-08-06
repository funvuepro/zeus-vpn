import enum
from sqlalchemy import BigInteger, Boolean, Column, DateTime, Enum, ForeignKey, Numeric, String, Integer, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class SubscriptionStatus(enum.Enum):
    active = "active"
    expired = "expired"
    cancelled = "cancelled"


class PaymentStatus(enum.Enum):
    pending = "pending"
    paid = "paid"
    failed = "failed"


class PaymentProvider(enum.Enum):
    cryptobot = "cryptobot"
    lava = "lava"
    freekassa = "freekassa"


class ReferralStatus(enum.Enum):
    pending = "pending"
    withdrawn = "withdrawn"


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
    marzban_username = Column(String, unique=True, nullable=True)
    remnawave_uuid = Column(String, unique=True, nullable=True)
    referred_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    display_id = Column(Integer, unique=True, nullable=True)
    bonus_days = Column(Integer, default=0, nullable=False, server_default="0")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_banned = Column(Boolean, nullable=False, server_default="false", default=False)
    is_admin = Column(Boolean, default=False, nullable=False, server_default="false")
    terms_accepted = Column(Boolean, default=False, nullable=False, server_default="false")
    terms_accepted_at = Column(DateTime(timezone=True), nullable=True)


class Plan(Base):
    __tablename__ = "plans"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    devices_limit = Column(Integer, nullable=False)
    duration_days = Column(Integer, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    is_active = Column(Boolean, nullable=False, server_default="true", default=True)


class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    plan_id = Column(Integer, ForeignKey("plans.id"), nullable=True)
    devices_limit = Column(Integer, nullable=False)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(Enum(SubscriptionStatus), default=SubscriptionStatus.active, nullable=False)
    is_trial = Column(Boolean, default=False, nullable=False, server_default="0")
    trial_notified = Column(Boolean, default=False, nullable=False, server_default="0")


class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    plan_id = Column(Integer, ForeignKey("plans.id"), nullable=False)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=True)
    provider = Column(Enum(PaymentProvider), nullable=False)
    external_id = Column(String, unique=True, nullable=True)
    amount = Column(Numeric(10, 2), nullable=False)
    promo_code_id = Column(Integer, ForeignKey("promo_codes.id"), nullable=True)
    devices_count = Column(Integer, nullable=True)
    is_upgrade = Column(Boolean, default=False, nullable=False, server_default="false")
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


class ReferralTransaction(Base):
    __tablename__ = "referral_transactions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    referrer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=False, unique=True)
    amount = Column(Numeric(10, 2), nullable=False)
    status = Column(Enum(ReferralStatus), default=ReferralStatus.pending, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class WithdrawalProvider(enum.Enum):
    cryptobot = "cryptobot"
    lava = "lava"


class WithdrawalStatus(enum.Enum):
    pending = "pending"
    sent = "sent"
    failed = "failed"


class CryptoType(enum.Enum):
    USDT = "USDT"
    TON = "TON"


class Withdrawal(Base):
    __tablename__ = "withdrawals"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    amount = Column(Numeric(10, 2), nullable=False)
    provider = Column(Enum(WithdrawalProvider), nullable=False)
    wallet_address = Column(String, nullable=False)
    crypto_type = Column(Enum(CryptoType), nullable=True)
    status = Column(Enum(WithdrawalStatus), default=WithdrawalStatus.pending, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class VpnServer(Base):
    __tablename__ = "vpn_servers"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    ip = Column(String, nullable=False)
    port = Column(Integer, nullable=False, default=443)
    transport = Column(String, nullable=False, default="tcp")  # "tcp" or "grpc"
    public_key = Column(String, nullable=False)
    short_id = Column(String, nullable=False)
    server_name = Column(String, nullable=False)  # SNI, e.g. "max.ru"
    fingerprint = Column(String, nullable=False, default="firefox")  # "firefox", "chrome", "qq"
    service_name = Column(String, nullable=True)  # gRPC service name
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    is_backup = Column(Boolean, nullable=False, default=False, server_default="false")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


