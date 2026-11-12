"""Preserve hostname targets and per-address TCP observations.

Revision ID: 35ae702d91c4
Revises: 72e4c01a39bf
"""

from ipaddress import IPv4Address

import sqlalchemy as sa
from alembic import op

revision = "35ae702d91c4"
down_revision = "72e4c01a39bf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        for table in ("scan_runs", "scan_jobs"):
            op.alter_column(
                table,
                "target",
                existing_type=sa.String(45),
                type_=sa.String(253),
                existing_nullable=False,
            )
    op.add_column(
        "tcp_port_results", sa.Column("ip_address", sa.String(15), nullable=True)
    )
    op.execute(
        sa.text(
            "UPDATE tcp_port_results SET ip_address = "
            "(SELECT target FROM scan_runs WHERE scan_runs.id = tcp_port_results.scan_id)"
        )
    )
    with op.batch_alter_table("tcp_port_results") as batch:
        batch.alter_column("ip_address", existing_type=sa.String(15), nullable=False)
        batch.drop_constraint("uq_tcp_port_results_scan_port", type_="unique")
        batch.create_unique_constraint(
            "uq_tcp_port_results_scan_ip_port", ["scan_id", "ip_address", "port"]
        )


def downgrade() -> None:
    # Never silently discard which destination produced historical evidence.
    connection = op.get_bind()
    for target in connection.execute(
        sa.text("SELECT target FROM scan_runs UNION SELECT target FROM scan_jobs")
    ).scalars():
        try:
            IPv4Address(target)
        except ValueError as error:
            raise RuntimeError(
                "Cannot downgrade while hostname runs or jobs exist"
            ) from error
    different_address = connection.execute(
        sa.text(
            "SELECT 1 FROM tcp_port_results AS p JOIN scan_runs AS r ON p.scan_id = r.id "
            "WHERE p.ip_address != r.target LIMIT 1"
        )
    ).first()
    if different_address:
        raise RuntimeError(
            "Cannot downgrade while multi-address report evidence exists"
        )
    with op.batch_alter_table("tcp_port_results") as batch:
        batch.drop_constraint("uq_tcp_port_results_scan_ip_port", type_="unique")
        batch.create_unique_constraint(
            "uq_tcp_port_results_scan_port", ["scan_id", "port"]
        )
        batch.drop_column("ip_address")
    if connection.dialect.name != "sqlite":
        for table in ("scan_runs", "scan_jobs"):
            op.alter_column(
                table,
                "target",
                existing_type=sa.String(253),
                type_=sa.String(45),
                existing_nullable=False,
            )
