"""Database evidence for a single TCP port in a completed scan."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base_model import BaseModel

if TYPE_CHECKING:
    from .scan_run import ScanRun


class TCPPortResult(BaseModel):
    """A port observation, not a service identification or vulnerability claim."""

    __tablename__ = "tcp_port_results"
    __table_args__ = (
        UniqueConstraint("scan_id", "port", name="uq_tcp_port_results_scan_port"),
        CheckConstraint("port BETWEEN 1 AND 65535", name="ck_tcp_port_results_port"),
        CheckConstraint(
            "state IN ('open', 'closed', 'unknown')", name="ck_tcp_port_results_state"
        ),
    )

    scan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "scan_runs.id",
            name="fk_tcp_port_results_scan_id_scan_runs",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    port: Mapped[int] = mapped_column(nullable=False)
    state: Mapped[str] = mapped_column(String(7), nullable=False)
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    error_number: Mapped[int | None] = mapped_column(nullable=True)

    scan_run: Mapped[ScanRun] = relationship(back_populates="tcp_port_results")
