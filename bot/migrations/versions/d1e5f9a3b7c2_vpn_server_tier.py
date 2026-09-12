"""vpn server 3-tier cascade (msk/lte/llp) instead of is_backup

Revision ID: d1e5f9a3b7c2
Revises: c4a7e91f2b3d
Create Date: 2026-09-12
"""
from alembic import op
import sqlalchemy as sa

revision = "d1e5f9a3b7c2"
down_revision = "c4a7e91f2b3d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "vpn_servers",
        sa.Column("tier", sa.String(), nullable=False, server_default="msk"),
    )
    op.execute("UPDATE vpn_servers SET tier = 'lte' WHERE is_backup = true")
    op.drop_column("vpn_servers", "is_backup")


def downgrade() -> None:
    op.add_column(
        "vpn_servers",
        sa.Column("is_backup", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.execute("UPDATE vpn_servers SET is_backup = true WHERE tier != 'msk'")
    op.drop_column("vpn_servers", "tier")
