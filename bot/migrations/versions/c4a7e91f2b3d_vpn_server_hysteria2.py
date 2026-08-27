"""vpn server hysteria2 support

Revision ID: c4a7e91f2b3d
Revises: 0f2380108c3f
Create Date: 2026-08-27
"""
from alembic import op
import sqlalchemy as sa

revision = "c4a7e91f2b3d"
down_revision = "0f2380108c3f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "vpn_servers",
        sa.Column("protocol", sa.String(), nullable=False, server_default="vless"),
    )
    op.add_column("vpn_servers", sa.Column("auth_password", sa.String(), nullable=True))
    op.alter_column("vpn_servers", "public_key", existing_type=sa.String(), nullable=True)
    op.alter_column("vpn_servers", "short_id", existing_type=sa.String(), nullable=True)
    op.alter_column("vpn_servers", "server_name", existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    op.alter_column("vpn_servers", "server_name", existing_type=sa.String(), nullable=False)
    op.alter_column("vpn_servers", "short_id", existing_type=sa.String(), nullable=False)
    op.alter_column("vpn_servers", "public_key", existing_type=sa.String(), nullable=False)
    op.drop_column("vpn_servers", "auth_password")
    op.drop_column("vpn_servers", "protocol")
