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

    op.drop_table("withdrawals")
    op.drop_table("referral_transactions")
    op.drop_table("subscriptions")

    # payments.plan_id, payments.subscription_id (init) and payments.promo_code_id (promo_codes
    # migration) are guaranteed to exist in this chain. payments.devices_count and
    # payments.is_upgrade were only ever present on the ORM model (never created by a migration
    # in this chain), so they are dropped defensively with IF EXISTS.
    op.drop_column("payments", "plan_id")
    op.drop_column("payments", "subscription_id")
    op.drop_column("payments", "promo_code_id")
    op.execute("ALTER TABLE payments DROP COLUMN IF EXISTS devices_count")
    op.execute("ALTER TABLE payments DROP COLUMN IF EXISTS is_upgrade")

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
