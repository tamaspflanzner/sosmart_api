"""track first team join

Revision ID: e215cf3185d4
Revises: a47c2ed48072
Create Date: 2026-10-18 15:18:21.867808

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e215cf3185d4'
down_revision: Union[str, Sequence[str], None] = 'a47c2ed48072'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add a permanent record of whether a user has joined a team."""

    op.add_column(
        "users",
        sa.Column(
            "has_joined_team",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    # Existing users who currently belong to a team have joined before.
    # Also recognize users who previously earned points for a team,
    # even if they are no longer members.
    op.execute(
        """
        UPDATE users
        SET has_joined_team = TRUE
        WHERE team_id IS NOT NULL
           OR id IN (
            SELECT DISTINCT user_id
            FROM study_trips
            WHERE team_id IS NOT NULL
        )
           OR id IN (
            SELECT DISTINCT user_id
            FROM team_members
        )
        """
    )


def downgrade() -> None:
    """Remove the team-joining history flag."""
    op.drop_column("users", "has_joined_team")