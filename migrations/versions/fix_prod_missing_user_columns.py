"""reconcile existing production schema

Revision ID: fix_prod_missing_user_columns
Revises: 5ceb620f3c5c
Create Date: 2026-06-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "fix_prod_missing_user_columns"
down_revision: Union[str, Sequence[str], None] = "5ceb620f3c5c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return False
    return column_name in [column["name"] for column in inspector.get_columns(table_name)]


def _has_index(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        return False
    return index_name in [index["name"] for index in inspector.get_indexes(table_name)]


def upgrade() -> None:
    # users table additions
    if _table_exists("users"):
        if not _has_column("users", "is_admin"):
            op.add_column(
                "users",
                sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            )

        if not _has_column("users", "line_id"):
            op.add_column("users", sa.Column("line_id", sa.String(length=255), nullable=True))

        if not _has_index("users", "ix_users_line_id") and _has_column("users", "line_id"):
            op.create_index("ix_users_line_id", "users", ["line_id"], unique=False)

        if not _has_column("users", "team_id"):
            op.add_column("users", sa.Column("team_id", sa.Integer(), nullable=True))

        if not _has_index("users", "ix_users_team_id") and _has_column("users", "team_id"):
            op.create_index("ix_users_team_id", "users", ["team_id"], unique=False)

    # teams table
    if not _table_exists("teams"):
        op.create_table(
            "teams",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("total_co2_saved_kg", sa.Float(), nullable=False, server_default="0"),
            sa.Column("total_trips", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_distance_km", sa.Float(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name"),
        )

    if _table_exists("teams") and not _has_index("teams", "ix_teams_id"):
        op.create_index("ix_teams_id", "teams", ["id"], unique=False)

    # study_trips.points
    if _table_exists("study_trips") and not _has_column("study_trips", "points"):
        op.add_column("study_trips", sa.Column("points", sa.Integer(), nullable=True))

    # team_members table
    if not _table_exists("team_members"):
        op.create_table(
            "team_members",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("team_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_team_members_id", "team_members", ["id"], unique=False)
        op.create_index("ix_team_members_team_id", "team_members", ["team_id"], unique=False)
        op.create_index("ix_team_members_user_id", "team_members", ["user_id"], unique=False)

    # password_reset_tokens table
    if not _table_exists("password_reset_tokens"):
        op.create_table(
            "password_reset_tokens",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("token_hash", sa.String(length=255), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_password_reset_tokens_id", "password_reset_tokens", ["id"], unique=False)
        op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"], unique=False)
        op.create_index("ix_password_reset_tokens_token_hash", "password_reset_tokens", ["token_hash"], unique=False)


def downgrade() -> None:
    pass