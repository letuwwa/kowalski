"""Store bounded service observations alongside completed TCP reports."""

import json

import sqlalchemy as sa
from alembic import op

revision = "a62b9d7140ec"
down_revision = "35ae702d91c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "scan_runs", sa.Column("services", sa.JSON(none_as_null=True), nullable=True)
    )


def downgrade() -> None:
    connection = op.get_bind()
    values = connection.execute(sa.text("SELECT services FROM scan_runs")).scalars()
    # Empty observations may be discarded; collected evidence must be preserved.
    if any(
        (json.loads(value) if isinstance(value, str) else value) for value in values
    ):
        raise RuntimeError("Cannot downgrade while service observations exist")
    op.drop_column("scan_runs", "services")
