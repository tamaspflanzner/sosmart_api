"""merge production schema and deleted user team points heads

Revision ID: 365fae9af841
Revises: a47c2ed48072, fix_prod_missing_user_columns
Create Date: 2026-10-05 19:34:12.949170

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '365fae9af841'
down_revision: Union[str, Sequence[str], None] = ('a47c2ed48072', 'fix_prod_missing_user_columns')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
