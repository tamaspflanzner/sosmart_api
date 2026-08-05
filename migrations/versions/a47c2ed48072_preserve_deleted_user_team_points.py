"""preserve deleted user team points

Revision ID: a47c2ed48072
Revises: 5ceb620f3c5c
Create Date: 2026-07-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a47c2ed48072"
down_revision: Union[str, None] = "5ceb620f3c5c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "teams",
        sa.Column(
            "preserved_points",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    op.drop_column("teams", "preserved_points")