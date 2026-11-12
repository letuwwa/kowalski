"""Add durable API scan jobs.

Revision ID: 72e4c01a39bf
Revises: 9b7106cd24ef
"""

import sqlalchemy as sa
from alembic import op

revision = "72e4c01a39bf"
down_revision = "9b7106cd24ef"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scan_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("target", sa.String(45), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(9), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.Text()),
        sa.Column("report_id", sa.Uuid()),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["report_id"], ["scan_runs.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("report_id"),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')",
            name="ck_scan_jobs_status",
        ),
        sa.CheckConstraint(
            "(status = 'completed' AND report_id IS NOT NULL) OR "
            "(status != 'completed' AND report_id IS NULL)",
            name="ck_scan_jobs_report",
        ),
    )
    op.create_index(
        "ix_scan_jobs_owner_created", "scan_jobs", ["user_id", "created_at", "id"]
    )
    op.create_index(
        "ix_scan_jobs_status_created", "scan_jobs", ["status", "created_at", "id"]
    )


def downgrade() -> None:
    op.drop_index("ix_scan_jobs_status_created", table_name="scan_jobs")
    op.drop_index("ix_scan_jobs_owner_created", table_name="scan_jobs")
    op.drop_table("scan_jobs")
