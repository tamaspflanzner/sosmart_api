"""add trip revocation fields

Revision ID: d551818df0d7
Revises: fb8101c015fd
Create Date: 2026-10-31 17:51:12.026107

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd551818df0d7'
down_revision: Union[str, Sequence[str], None] = 'fb8101c015fd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "study_trips",
        sa.Column(
            "is_revoked",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.add_column(
        "study_trips",
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.add_column(
        "study_trips",
        sa.Column("revoke_reason", sa.String(length=255), nullable=True),
    )

    op.create_index(
        "ix_study_trips_is_revoked",
        "study_trips",
        ["is_revoked"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_study_trips_is_revoked", table_name="study_trips")
    op.drop_column("study_trips", "revoke_reason")
    op.drop_column("study_trips", "revoked_at")
    op.drop_column("study_trips", "is_revoked")