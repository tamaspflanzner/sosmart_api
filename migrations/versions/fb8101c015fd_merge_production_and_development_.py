"""merge production and development migration heads

Revision ID: fb8101c015fd
Revises: 365fae9af841, 4bfcebc42352
Create Date: 2026-10-18 23:16:12.876713

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fb8101c015fd'
down_revision: Union[str, Sequence[str], None] = ('365fae9af841', '4bfcebc42352')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
