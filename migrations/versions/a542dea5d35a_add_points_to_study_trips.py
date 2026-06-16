"""add points to study trips

Revision ID: a542dea5d35a
Revises: dfcd2111d184
Create Date: 2026-06-09 12:35:12.030835

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a542dea5d35a'
down_revision: Union[str, Sequence[str], None] = 'dfcd2111d184'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "study_trips",
        sa.Column("points", sa.Integer(), nullable=True),
    )



def downgrade() -> None:
    op.drop_column("study_trips", "points")
    pass
