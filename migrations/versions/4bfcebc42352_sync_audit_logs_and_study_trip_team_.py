
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
    connection = op.get_bind()
    dialect = connection.dialect.name

    def table_exists(table):
        return sa.inspect(connection).has_table(table)

    def columns_of(table):
        return {
            col["name"]: col
            for col in sa.inspect(connection).get_columns(table)
        }

    def indexes_of(table):
        return {
            idx["name"]
            for idx in sa.inspect(connection).get_indexes(table)
        }

    # 1. Ensure audit_logs exists without changing existing rows.
    if not table_exists("audit_logs"):
        op.create_table(
            "audit_logs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("admin_id", sa.Integer(), nullable=True),
            sa.Column("action", sa.String(100), nullable=False),
            sa.Column("entity_type", sa.String(50), nullable=False),
            sa.Column("entity_id", sa.Integer(), nullable=True),
            sa.Column("details", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column("admin_name", sa.String(255), nullable=False),
            sa.Column("admin_email", sa.String(255), nullable=False),
        )

    else:
        # 2. Add missing administrator columns when necessary.
        existing = columns_of("audit_logs")

        if "admin_id" not in existing:
            op.add_column(
                "audit_logs",
                sa.Column("admin_id", sa.Integer(), nullable=True),
            )

        for name in ("admin_name", "admin_email"):
            if name not in existing:
                op.add_column(
                    "audit_logs",
                    sa.Column(
                        name, sa.String(255), nullable=True
                    ),
                )

        # Existing audit rows must have administrator details.
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
                f"{missing} audit logs have missing admin details. "
                "Backfill using verified historical information "
                "before enforcing NOT NULL."
            )

        # 3. Inspect the real foreign key.
        foreign_keys = sa.inspect(connection).get_foreign_keys(
            "audit_logs"
        )

        admin_fk = next(
            (
                fk for fk in foreign_keys
                if fk["constrained_columns"] == ["admin_id"]
                   and fk["referred_table"] == "users"
                   and fk["referred_columns"] == ["id"]
            ),
            None,
        )

        if dialect == "sqlite":
            fk_name = (
                "fk_audit_logs_admin_id_users"
                if admin_fk else None
            )
        else:
            fk_name = admin_fk["name"] if admin_fk else None

            if admin_fk and not fk_name:
                raise RuntimeError(
                    "Cannot identify existing admin foreign key."
                )

        # 4. Apply the final model nullability and FK structure.
        with op.batch_alter_table(
                "audit_logs",
                recreate="always" if dialect == "sqlite" else "auto",
                naming_convention=(
                        naming_convention if dialect == "sqlite" else None
                ),
        ) as batch_op:

            batch_op.alter_column(
                "admin_id",
                existing_type=sa.Integer(),
                nullable=True,
            )

            batch_op.alter_column(
                "admin_name",
                existing_type=sa.String(255),
                nullable=False,
            )

            batch_op.alter_column(
                "admin_email",
                existing_type=sa.String(255),
                nullable=False,
            )

            if fk_name:
                batch_op.drop_constraint(
                    fk_name,
                    type_="foreignkey",
                )



    # Ensure audit_log indexes match the SQLAlchemy model.
    audit_indexes = indexes_of("audit_logs")

    if "ix_audit_logs_admin_id" not in audit_indexes:
        op.create_index(
            "ix_audit_logs_admin_id",
            "audit_logs",
            ["admin_id"],
            unique=False,
        )

    if "ix_audit_logs_created_at" not in audit_indexes:
        op.create_index(
            "ix_audit_logs_created_at",
            "audit_logs",
            ["created_at"],
            unique=False,
        )



    # 5. Ensure study_trips.team_id exists.
    if not table_exists("study_trips"):
        raise RuntimeError("study_trips table is missing")


    trip_columns = columns_of("study_trips")

    if "team_id" not in trip_columns:
        op.add_column(
            "study_trips",
            sa.Column("team_id", sa.Integer(), nullable=True),
        )

    # Check whether the foreign key already exists.
    trip_foreign_keys = sa.inspect(connection).get_foreign_keys(
        "study_trips"
    )

    has_team_fk = any(
        fk["constrained_columns"] == ["team_id"]
        and fk["referred_table"] == "teams"
        and fk["referred_columns"] == ["id"]
        for fk in trip_foreign_keys
    )

    if not has_team_fk:
        # Do not attempt to add a constraint to invalid data.
        invalid_teams = connection.execute(
            sa.text("""
                    SELECT COUNT(*)
                    FROM study_trips AS st
                             LEFT JOIN teams AS t ON t.id = st.team_id
                    WHERE st.team_id IS NOT NULL
                      AND t.id IS NULL
                    """)
        ).scalar_one()

        if invalid_teams:
            raise RuntimeError(
                f"Cannot add team foreign key: {invalid_teams} "
                "trips reference nonexistent teams."
            )

        with op.batch_alter_table(
                "study_trips",
                recreate="always" if dialect == "sqlite" else "auto",
        ) as batch_op:
            batch_op.create_foreign_key(
                "fk_study_trips_team_id_teams",
                "teams",
                ["team_id"],
                ["id"],
            )

    if "ix_study_trips_team_id" not in indexes_of("study_trips"):
        op.create_index(
            "ix_study_trips_team_id",
            "study_trips",
            ["team_id"],
            unique=False,
        )



    # Ensure users.line_id has the uniqueness required by the model.
    duplicate_count = connection.execute(
        sa.text("""
                SELECT COUNT(*)
                FROM (
                         SELECT line_id
                         FROM users
                         WHERE line_id IS NOT NULL
                         GROUP BY line_id
                         HAVING COUNT(*) > 1
                     ) AS duplicate_ids
                """)
    ).scalar_one()

    if duplicate_count:
        raise RuntimeError(
            f"Cannot create unique LINE ID index: "
            f"{duplicate_count} duplicated LINE IDs exist."
        )

    user_indexes = {
        idx["name"]: idx
        for idx in sa.inspect(connection).get_indexes("users")
    }

    line_index = user_indexes.get("ix_users_line_id")

    if line_index is not None and not line_index["unique"]:
        op.drop_index(
            "ix_users_line_id",
            table_name="users",
        )

    if line_index is None or not line_index["unique"]:
        op.create_index(
            "ix_users_line_id",
            "users",
            ["line_id"],
            unique=True,
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
            recreate="always" if connection.dialect.name == "sqlite" else "auto",
            naming_convention=(
                    naming_convention
                    if connection.dialect.name == "sqlite"
                    else None
            ),
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
