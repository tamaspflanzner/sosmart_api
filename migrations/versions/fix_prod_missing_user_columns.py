"""fix prod missing user columns

Revision ID: fix_prod_missing_user_columns
Revises: a542dea5d35a
Create Date: 2026-06-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "fix_prod_missing_user_columns"
down_revision: Union[str, Sequence[str], None] = "a542dea5d35a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column_name in [column["name"] for column in inspector.get_columns(table_name)]


def upgrade() -> None:
    if not _has_column("users", "line_id"):
        op.add_column("users", sa.Column("line_id", sa.String(length=255), nullable=True))
        op.create_index(op.f("ix_users_line_id"), "users", ["line_id"], unique=False)

    if not _has_column("users", "team_id"):
        op.add_column("users", sa.Column("team_id", sa.Integer(), nullable=True))
        op.create_index(op.f("ix_users_team_id"), "users", ["team_id"], unique=False)
        op.create_foreign_key(
            "fk_users_team_id_teams",
            "users",
            "teams",
            ["team_id"],
            ["id"],
        )


def downgrade() -> None:
    if _has_column("users", "team_id"):
        op.drop_constraint("fk_users_team_id_teams", "users", type_="foreignkey")
        op.drop_index(op.f("ix_users_team_id"), table_name="users")
        op.drop_column("users", "team_id")

    if _has_column("users", "line_id"):
        op.drop_index(op.f("ix_users_line_id"), table_name="users")
        op.drop_column("users", "line_id")