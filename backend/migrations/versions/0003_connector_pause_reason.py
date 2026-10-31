"""Connector pause reason, set when an auth error pauses syncing

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-29
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("connectors", schema=None) as batch_op:
        batch_op.add_column(sa.Column("pause_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("connectors", schema=None) as batch_op:
        batch_op.drop_column("pause_reason")
