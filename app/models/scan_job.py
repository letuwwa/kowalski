"""Durable API scan requests, separate from completed report snapshots."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base_model import BaseModel


class ScanJob(BaseModel):
    __tablename__ = "scan_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')",
            name="ck_scan_jobs_status",
        ),
        CheckConstraint(
            "(status = 'completed' AND report_id IS NOT NULL) OR "
            "(status != 'completed' AND report_id IS NULL)",
            name="ck_scan_jobs_report",
        ),
        Index("ix_scan_jobs_owner_created", "user_id", "created_at", "id"),
        Index("ix_scan_jobs_status_created", "status", "created_at", "id"),
    )

    # Explicit precision keeps SQLite keyset comparisons consistent with bound
    # datetime parameters; the server default still supports direct inserts.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    target: Mapped[str] = mapped_column(String(45), nullable=False)
    configuration: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(9), default="queued", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("scan_runs.id", ondelete="RESTRICT"), unique=True
    )
