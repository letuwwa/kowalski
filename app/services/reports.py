"""Map engine reports to database records without coupling the engine to SQLAlchemy."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import ScanRun, TCPPortResult
from engine.report import ScanConfiguration, ScanReport
from engine.services.tcp import PortState
from engine.services.tcp import TCPPortResult as PortObservation


def utc(value: datetime) -> datetime:
    """SQLite returns naive UTC; PostgreSQL may return a different aware offset."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def report_from_run(run: ScanRun) -> ScanReport:
    config = run.configuration
    return ScanReport(
        id=run.id,
        target=run.target,
        started_at=utc(run.started_at),
        completed_at=utc(run.completed_at),
        configuration=ScanConfiguration(
            ports=tuple(config["ports"]),
            allowed_targets=tuple(config["allowed_targets"]),
            timeout=config["timeout"],
            concurrency=config["concurrency"],
            rate_limit=config["rate_limit"],
        ),
        results={
            "tcp": [
                PortObservation(
                    run.target,
                    row.port,
                    PortState(row.state),
                    row.evidence,
                    row.error_number,
                )
                for row in run.tcp_port_results
            ]
        },
    )


def store_report(report: ScanReport, owner_id: UUID) -> ScanRun:
    """Flush a report atomically; the caller commits the surrounding transaction.

    Identical retries are idempotent. Conflicting IDs never overwrite evidence
    or disclose another owner's report. A savepoint handles concurrent inserts.
    """
    if set(report.results) != {"tcp"}:
        raise ValueError("Only TCP reports can be stored")
    existing = db.session.get(ScanRun, report.id)
    if existing is None:
        try:
            with db.session.begin_nested():
                run = ScanRun(
                    id=report.id,
                    user_id=owner_id,
                    target=report.target,
                    started_at=report.started_at,
                    completed_at=report.completed_at,
                    configuration=report.configuration.to_dict(),
                    schema_version=1,
                    tcp_port_results=[
                        TCPPortResult(
                            port=row.port,
                            state=row.state.value,
                            evidence=row.evidence,
                            error_number=row.error_number,
                        )
                        for row in report.results["tcp"]
                    ],
                )
                db.session.add(run)
                db.session.flush()
            return run
        except IntegrityError:
            existing = db.session.get(ScanRun, report.id)
            if existing is None:
                raise
    if (
        existing.user_id != owner_id
        or report_from_run(existing).to_dict() != report.to_dict()
    ):
        raise ValueError("Report ID conflicts with an existing report")
    return existing
