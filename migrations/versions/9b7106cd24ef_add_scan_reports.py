"""Add owned completed scan runs and TCP port evidence.

Revision ID: 9b7106cd24ef
Revises: ecf7573043bc
"""

import sqlalchemy as sa
from alembic import op

revision = "9b7106cd24ef"
down_revision = "ecf7573043bc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scan_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("target", sa.String(45), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("configuration", sa.JSON(none_as_null=True), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_scan_runs_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "completed_at >= started_at", name="ck_scan_runs_timestamps"
        ),
        sa.CheckConstraint("schema_version >= 1", name="ck_scan_runs_schema_version"),
    )
    op.create_index(
        "ix_scan_runs_user_started", "scan_runs", ["user_id", "started_at", "id"]
    )
    op.create_table(
        "tcp_port_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scan_id", sa.Uuid(), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(7), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("error_number", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["scan_id"],
            ["scan_runs.id"],
            name="fk_tcp_port_results_scan_id_scan_runs",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("scan_id", "port", name="uq_tcp_port_results_scan_port"),
        sa.CheckConstraint("port BETWEEN 1 AND 65535", name="ck_tcp_port_results_port"),
        sa.CheckConstraint(
            "state IN ('open', 'closed', 'unknown')", name="ck_tcp_port_results_state"
        ),
    )


def downgrade() -> None:
    op.drop_table("tcp_port_results")
    op.drop_index("ix_scan_runs_user_started", table_name="scan_runs")
    op.drop_table("scan_runs")
