"""promo codes

Revision ID: b3f8a2c9d1e5
Revises: 7809f86894f4
Create Date: 2026-05-21
"""
from alembic import op
import sqlalchemy as sa

revision = "b3f8a2c9d1e5"
down_revision = "7809f86894f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "promo_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(32), unique=True, nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
    )
    op.create_table(
        "promo_code_usages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("promo_code_id", sa.Integer(), sa.ForeignKey("promo_codes.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.UniqueConstraint("promo_code_id", "user_id", name="uq_promo_usage"),
    )
    op.add_column("users", sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("payments", sa.Column("promo_code_id", sa.Integer(), sa.ForeignKey("promo_codes.id"), nullable=True))


def downgrade() -> None:
    op.drop_column("payments", "promo_code_id")
    op.drop_column("users", "is_admin")
    op.drop_table("promo_code_usages")
    op.drop_table("promo_codes")
