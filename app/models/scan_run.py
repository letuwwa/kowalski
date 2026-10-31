"""Stored completed scans owned by an application user."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base_model import BaseModel

if TYPE_CHECKING:
    from .tcp_port_result import TCPPortResult
    from .user import User


class ScanRun(BaseModel):
    """A completed report snapshot; callers must supply the engine's report UUID.

    Configuration is stored as JSON; assign a new dictionary when changing it.
    Scan timestamps describe execution, while inherited timestamps describe
    database storage. Persistence and access control belong to the API layer.
    """

    __tablename__ = "scan_runs"
    __table_args__ = (
        CheckConstraint("completed_at >= started_at", name="ck_scan_runs_timestamps"),
        CheckConstraint("schema_version >= 1", name="ck_scan_runs_schema_version"),
        Index("ix_scan_runs_user_started", "user_id", "started_at", "id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", name="fk_scan_runs_user_id_users", ondelete="RESTRICT"),
        nullable=False,
    )
    target: Mapped[str] = mapped_column(String(45), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    configuration: Mapped[dict[str, object]] = mapped_column(
        JSON(none_as_null=True), nullable=False
    )
    schema_version: Mapped[int] = mapped_column(nullable=False)

    user: Mapped[User] = relationship(back_populates="scan_runs")
    tcp_port_results: Mapped[list[TCPPortResult]] = relationship(
        back_populates="scan_run",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TCPPortResult.port",
    )
