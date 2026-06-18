"""add audio path to assets

Revision ID: 9b6f5c1e2a70
Revises: 7fb52d06b50e
Create Date: 2026-06-18 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9b6f5c1e2a70"
down_revision: str | Sequence[str] | None = "7fb52d06b50e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("assets", schema=None) as batch_op:
        batch_op.add_column(sa.Column("audio_path", sa.String(length=500), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("assets", schema=None) as batch_op:
        batch_op.drop_column("audio_path")
