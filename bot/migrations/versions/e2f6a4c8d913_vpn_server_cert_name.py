"""vpn server cert_name for hysteria2 peer cert verification

Revision ID: e2f6a4c8d913
Revises: d1e5f9a3b7c2
Create Date: 2026-09-14
"""
from alembic import op
import sqlalchemy as sa

revision = "e2f6a4c8d913"
down_revision = "d1e5f9a3b7c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("vpn_servers", sa.Column("cert_name", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("vpn_servers", "cert_name")
