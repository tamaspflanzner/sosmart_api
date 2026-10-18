
"""Sync audit logs constraints and study trip team index.

Revision ID: 4bfcebc42352
Revises: e215cf3185d4
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4bfcebc42352"
down_revision: Union[str, Sequence[str], None] = "e215cf3185d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Assign a temporary name to the existing unnamed SQLite foreign key.
naming_convention = {
    "fk": (
        "fk_%(table_name)s_%(column_0_name)s_"
        "%(referred_table_name)s"
    ),
}


def upgrade() -> None:
    # Validate existing records before enforcing NOT NULL.
    connection = op.get_bind()

    missing = connection.execute(
        sa.text("""
                SELECT COUNT(*)
                FROM audit_logs
                WHERE admin_name IS NULL
                   OR admin_email IS NULL
                """)
    ).scalar_one()

    if missing:
        raise RuntimeError(
            f"Cannot upgrade: {missing} audit logs contain "
            "NULL administrator names or emails."
        )

    # SQLite requires table recreation for these schema changes.
    with op.batch_alter_table(
            "audit_logs",
            recreate="always",
            naming_convention=naming_convention,
    ) as batch_op:

        batch_op.alter_column(
            "admin_id",
            existing_type=sa.Integer(),
            nullable=True,
        )

        batch_op.alter_column(
            "admin_name",
            existing_type=sa.String(length=255),
            nullable=False,
        )

        batch_op.alter_column(
            "admin_email",
            existing_type=sa.String(length=255),
            nullable=False,
        )

        batch_op.drop_constraint(
            "fk_audit_logs_admin_id_users",
            type_="foreignkey",
        )

    op.create_index(
        "ix_study_trips_team_id",
        "study_trips",
        ["team_id"],
        unique=False,
    )


def downgrade() -> None:
    connection = op.get_bind()

    # Restoring the old schema requires valid administrator IDs.
    invalid = connection.execute(
        sa.text("""
                SELECT COUNT(*)
                FROM audit_logs AS a
                         LEFT JOIN users AS u ON u.id = a.admin_id
                WHERE a.admin_id IS NULL
                   OR u.id IS NULL
                """)
    ).scalar_one()

    if invalid:
        raise RuntimeError(
            f"Cannot downgrade: {invalid} audit logs have "
            "NULL or nonexistent administrator IDs."
        )

    op.drop_index(
        "ix_study_trips_team_id",
        table_name="study_trips",
    )

    with op.batch_alter_table(
            "audit_logs",
            recreate="always",
            naming_convention=naming_convention,
    ) as batch_op:

        batch_op.alter_column(
            "admin_id",
            existing_type=sa.Integer(),
            nullable=False,
        )

        batch_op.alter_column(
            "admin_name",
            existing_type=sa.String(length=255),
            nullable=True,
        )

        batch_op.alter_column(
            "admin_email",
            existing_type=sa.String(length=255),
            nullable=True,
        )

        batch_op.create_foreign_key(
            "fk_audit_logs_admin_id_users",
            "users",
            ["admin_id"],
            ["id"],
        )
