"""Scan reports with separate JSON and future database representations."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from ipaddress import IPv4Address
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from engine.services.tcp import TCPPortResult


@dataclass(frozen=True)
class ServiceObservation:
    ip_address: str
    port: int
    status: str
    evidence_base64: str
    protocol: str | None = None
    banner: str | None = None
    protocol_version: str | None = None
    advertised_software: str | None = None
    confidence: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ScanConfiguration:
    ports: tuple[int, ...]
    allowed_targets: tuple[str, ...]
    timeout: float
    concurrency: int
    rate_limit: float

    service_ports: tuple[int, ...] | None = None

    def to_dict(self) -> dict[str, object]:
        """Return JSON-compatible configuration suitable for a JSON column."""
        return {
            **(
                {"service_ports": list(self.service_ports)}
                if self.service_ports is not None
                else {}
            ),
            "ports": list(self.ports),
            "allowed_targets": list(self.allowed_targets),
            "timeout": self.timeout,
            "concurrency": self.concurrency,
            "rate_limit": self.rate_limit,
        }


@dataclass
class ScanReport:
    """A completed scan, independent of Flask, database sessions, and ORM models.

    Future SQLAlchemy models can use Uuid for id, DateTime(timezone=True) for
    timestamps, and JSON/JSONB for configuration and results. No database writes
    occur here. Failed or cancelled scans do not produce a completed report.
    """

    target: str
    configuration: ScanConfiguration
    started_at: datetime
    completed_at: datetime
    results: dict[str, list[TCPPortResult]]
    id: UUID = field(default_factory=uuid4)
    schema_version: int = 3
    services: list[ServiceObservation] = field(default_factory=list)

    def __post_init__(self) -> None:
        for timestamp in (self.started_at, self.completed_at):
            if timestamp.utcoffset() is None:
                raise ValueError("Report timestamps must be timezone-aware")
        if self.completed_at < self.started_at:
            raise ValueError("Completion must not precede scan start")
        self.started_at = self.started_at.astimezone(UTC)
        self.completed_at = self.completed_at.astimezone(UTC)

    @property
    def resolved_ips(self) -> tuple[str, ...]:
        """Actual destinations represented in this completed report's evidence."""
        return tuple(
            sorted(
                {row.target for rows in self.results.values() for row in rows},
                key=IPv4Address,
            )
        )

    @property
    def summary(self) -> dict[str, dict[str, int]]:
        """Derive counts from evidence so stored results remain the source of truth."""
        return {
            scanner: {
                "total": len(results),
                "open": sum(result.state == "open" for result in results),
                "closed": sum(result.state == "closed" for result in results),
                "unknown": sum(result.state == "unknown" for result in results),
            }
            for scanner, results in self.results.items()
        }

    def to_record(self) -> dict[str, object]:
        """Keep native UUID/datetime values; nested payloads fit JSON columns.

        This is data for a future persistence adapter, not an ORM model or a
        database insert. Derived summary counts are deliberately not stored.
        """
        return {
            **(
                {"services": [row.to_dict() for row in self.services]}
                if self.schema_version >= 3
                else {}
            ),
            "schema_version": self.schema_version,
            "id": self.id,
            "target": self.target,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "configuration": self.configuration.to_dict(),
            "results": {
                scanner: [
                    {
                        "target": result.target,
                        "port": result.port,
                        "state": result.state.value,
                        "evidence": result.evidence,
                        "error_number": result.error_number,
                    }
                    for result in results
                ]
                for scanner, results in self.results.items()
            },
        }

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible report with derived summary counts."""
        return {
            **self.to_record(),
            "id": str(self.id),
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "summary": self.summary,
            "resolved_ips": list(self.resolved_ips),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, allow_nan=False)
