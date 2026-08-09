"""zeus vpn balance model

Revision ID: 0f2380108c3f
Revises: b3f8a2c9d1e5
Create Date: 2026-08-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0f2380108c3f"
down_revision = "b3f8a2c9d1e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- users: new balance-model fields ---
    op.add_column("users", sa.Column("balance", sa.Numeric(10, 2), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("devices_limit", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("users", sa.Column("access_active", sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("users", sa.Column("grace_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("referral_bonus_granted", sa.Boolean(), nullable=False, server_default="false"))

    # --- users: columns that bot/database/models.py has always had (since before this task) but that
    # were never created by any migration in this chain — only by VpnBot's old ad-hoc _init_db()
    # SQLite ALTER TABLE hack in bot/main.py (dev-only, SQLite-only, irrelevant to real Postgres
    # deployments). Added here so a Postgres database built purely from this migration chain matches
    # bot/database/models.py exactly, as later tasks (e.g. the balance service) read these columns
    # via the ORM.
    op.add_column("users", sa.Column("remnawave_uuid", sa.String(), nullable=True))
    op.create_unique_constraint("uq_users_remnawave_uuid", "users", ["remnawave_uuid"])
    op.add_column("users", sa.Column("display_id", sa.Integer(), nullable=True))
    op.create_unique_constraint("uq_users_display_id", "users", ["display_id"])
    op.add_column("users", sa.Column("terms_accepted", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("users", sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=True))

    # users.marzban_username was created by 7809f86894f4 (init) and is guaranteed to exist there;
    # users.bonus_days was only ever present on the ORM model (never created by an Alembic migration
    # in this chain), so it is dropped defensively with IF EXISTS to avoid failing on a database that
    # was built strictly from this migration chain.
    op.drop_column("users", "marzban_username")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS bonus_days")

    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("daily_rate_per_device", sa.Numeric(10, 2), nullable=False, server_default="1.00"),
    )
    op.execute("INSERT INTO app_settings (id, daily_rate_per_device) VALUES (1, 1.00)")

    # --- instructions / vpn_servers: net-new tables, present on the ORM models since the Task 1
    # bootstrap commit but never created by any migration in this chain. Without these, a Postgres
    # database built purely via `alembic upgrade head` would be missing both tables entirely, even
    # though this migration is meant to be the real source of truth for Postgres. Neither table has
    # a ForeignKey to another table or to `users`, so creation order relative to the rest of this
    # migration is not constrained.
    op.create_table(
        "instructions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "platform",
            sa.Enum("android", "ios", "windows", "macos", name="instructionplatform"),
            nullable=False,
        ),
        sa.Column(
            "category",
            sa.Enum("general", "connect", name="instructioncategory"),
            nullable=False,
        ),
        sa.Column("text", sa.String(), nullable=False),
        sa.UniqueConstraint("platform", "category", name="uq_instruction_platform_category"),
    )

    op.create_table(
        "vpn_servers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("ip", sa.String(), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("transport", sa.String(), nullable=False),
        sa.Column("public_key", sa.String(), nullable=False),
        sa.Column("short_id", sa.String(), nullable=False),
        sa.Column("server_name", sa.String(), nullable=False),
        sa.Column("fingerprint", sa.String(), nullable=False),
        sa.Column("service_name", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_backup", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # payments.plan_id, payments.subscription_id (init) and payments.promo_code_id (promo_codes
    # migration) are guaranteed to exist in this chain. payments.devices_count and
    # payments.is_upgrade were only ever present on the ORM model (never created by a migration
    # in this chain), so they are dropped defensively with IF EXISTS.
    #
    # These column drops MUST happen before dropping the "plans"/"subscriptions" tables they
    # reference via ForeignKey — otherwise Postgres refuses the DROP TABLE with
    # "cannot drop table ... because other objects depend on it".
    op.drop_column("payments", "plan_id")
    op.drop_column("payments", "subscription_id")
    op.drop_column("payments", "promo_code_id")
    op.execute("ALTER TABLE payments DROP COLUMN IF EXISTS devices_count")
    op.execute("ALTER TABLE payments DROP COLUMN IF EXISTS is_upgrade")

    op.drop_table("withdrawals")
    op.drop_table("referral_transactions")
    op.drop_table("subscriptions")
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
