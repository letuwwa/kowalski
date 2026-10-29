"""revoke token sessions

Revision ID: a1c7d93e840f
Revises: ecf7573043bc
Create Date: 2026-08-26

"""

import sqlalchemy as sa
from alembic import op

revision = "a1c7d93e840f"
down_revision = "ecf7573043bc"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("token_blocklist", schema=None) as batch_op:
        batch_op.add_column(sa.Column("session_id", sa.String(36), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_token_blocklist_session_id"),
            ["session_id"],
            unique=True,
        )


def downgrade():
    with op.batch_alter_table("token_blocklist", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_token_blocklist_session_id"))
        batch_op.drop_column("session_id")
