"""Validated API requests, owned history, and chronological observations."""

import math
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from ipaddress import IPv4Address
from uuid import UUID

from flask import current_app
from sqlalchemy import Select, and_, func, or_, select, text
from sqlalchemy.orm import InstrumentedAttribute, selectinload
from werkzeug.exceptions import BadRequest, TooManyRequests

from app.extensions import db
from app.models import ScanJob, ScanRun

from .reports import report_from_run, utc


def ipv4(value: object) -> str:
    if not isinstance(value, str):
        raise BadRequest("target must be a literal IPv4 address")
    try:
        return str(IPv4Address(value))
    except ValueError as error:
        raise BadRequest("target must be a literal IPv4 address") from error


def validate_scan(payload: object) -> tuple[str, dict[str, object]]:
    if not isinstance(payload, dict):
        raise BadRequest("Expected a JSON object")
    allowed_fields = {
        "target",
        "ports",
        "scanners",
        "timeout",
        "concurrency",
        "rate_limit",
    }
    if set(payload) - allowed_fields:
        raise BadRequest("Unsupported scan options")
    if payload.get("scanners", ["tcp"]) != ["tcp"]:
        raise BadRequest("Only scanners: ['tcp'] is supported")
    target = ipv4(payload.get("target"))
    config = current_app.config
    ports = payload.get("ports")
    if not isinstance(ports, list) or not 1 <= len(ports) <= config["SCAN_MAX_PORTS"]:
        raise BadRequest(f"ports must contain 1-{config['SCAN_MAX_PORTS']} integers")
    if any(type(port) is not int or not 1 <= port <= 65535 for port in ports):
        raise BadRequest("Ports must be integers between 1 and 65535")
    options = {}
    for name, default, maximum in (
        ("timeout", 1, config["SCAN_MAX_TIMEOUT"]),
        (
            "concurrency",
            min(20, config["SCAN_MAX_CONCURRENCY"]),
            config["SCAN_MAX_CONCURRENCY"],
        ),
        ("rate_limit", min(100, config["SCAN_MAX_RATE"]), config["SCAN_MAX_RATE"]),
    ):
        value = payload.get(name, default)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not 0 < value <= maximum
            or not math.isfinite(value)
        ):
            raise BadRequest(f"{name} must be positive and at most {maximum}")
        if name == "concurrency" and type(value) is not int:
            raise BadRequest("concurrency must be an integer")
        options[name] = value
    return target, {"ports": sorted(set(ports)), "allowed_targets": [target], **options}


def submit_scan(payload: object, owner_id: UUID) -> ScanJob:
    target, configuration = validate_scan(payload)
    # Serialize quota checks across API processes on the supported production DB.
    if db.engine.dialect.name == "postgresql":
        db.session.execute(text("SELECT pg_advisory_xact_lock(67204202)"))
    pending = select(ScanJob).where(ScanJob.status.in_(["queued", "running"]))
    total = db.session.scalar(select(func.count()).select_from(pending.subquery()))
    owned = db.session.scalar(
        select(func.count()).select_from(
            pending.where(ScanJob.user_id == owner_id).subquery()
        )
    )
    if (
        total >= current_app.config["SCAN_MAX_PENDING"]
        or owned >= current_app.config["SCAN_MAX_PENDING_PER_USER"]
    ):
        raise TooManyRequests("Scan queue is full; retry after pending scans finish")
    job = ScanJob(user_id=owner_id, target=target, configuration=configuration)
    db.session.add(job)
    db.session.commit()
    return job


def job_dict(job: ScanJob) -> dict[str, object]:
    return {
        "id": str(job.id),
        "target": job.target,
        "status": job.status,
        "created_at": utc(job.created_at).isoformat(),
        "started_at": utc(job.started_at).isoformat() if job.started_at else None,
        "completed_at": utc(job.completed_at).isoformat() if job.completed_at else None,
        "error": job.error,
    }


def timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.utcoffset() is None:
            raise ValueError
        return parsed.astimezone(UTC)
    except (ValueError, OverflowError) as error:
        raise BadRequest("Dates must be ISO 8601 timestamps with a timezone") from error


def paginate(
    query: Select,
    model: type[ScanJob | ScanRun],
    time_column: InstrumentedAttribute,
    args: Mapping[str, str],
    *,
    ascending: bool = False,
) -> tuple[Sequence[ScanJob | ScanRun], str | None]:
    """Keyset pagination, ordered deterministically by timestamp and UUID."""
    try:
        limit = int(args.get("limit", "20"))
        if not 1 <= limit <= 100:
            raise ValueError
    except ValueError as error:
        raise BadRequest("limit must be between 1 and 100") from error
    if cursor := args.get("cursor"):
        try:
            when, identifier = cursor.split("|")
            when, identifier = timestamp(when), UUID(identifier)
        except (ValueError, BadRequest) as error:
            raise BadRequest("Invalid pagination cursor") from error
        query = query.where(
            or_(
                time_column > when if ascending else time_column < when,
                and_(
                    time_column == when,
                    model.id > identifier if ascending else model.id < identifier,
                ),
            )
        )
    order = (
        (time_column.asc(), model.id.asc())
        if ascending
        else (time_column.desc(), model.id.desc())
    )
    rows = db.session.scalars(query.order_by(*order).limit(limit + 1)).all()
    page = rows[:limit]
    next_cursor = None
    if len(rows) > limit:
        last = page[-1]
        next_cursor = f"{utc(getattr(last, time_column.key)).isoformat()}|{last.id}"
    return page, next_cursor


def history(owner_id: UUID, target: str, args: Mapping[str, str]) -> dict[str, object]:
    query = select(ScanRun).where(ScanRun.user_id == owner_id, ScanRun.target == target)
    lower = timestamp(args["from"]) if args.get("from") else None
    upper = timestamp(args["to"]) if args.get("to") else None
    if lower and upper and lower > upper:
        raise BadRequest("from must not be later than to")
    if lower:
        query = query.where(ScanRun.started_at >= lower)
    if upper:
        query = query.where(ScanRun.started_at <= upper)
    runs, cursor = paginate(
        query.options(selectinload(ScanRun.tcp_port_results)),
        ScanRun,
        ScanRun.started_at,
        args,
        ascending=True,
    )
    previous = None
    if runs:
        first = runs[0]
        previous = db.session.scalar(
            select(ScanRun)
            .where(
                ScanRun.user_id == owner_id,
                ScanRun.target == target,
                or_(
                    ScanRun.started_at < first.started_at,
                    and_(ScanRun.started_at == first.started_at, ScanRun.id < first.id),
                ),
            )
            .order_by(ScanRun.started_at.desc(), ScanRun.id.desc())
            .limit(1)
        )
    items = []
    for run in runs:
        before = (
            {row.port: row.state for row in previous.tcp_port_results}
            if previous
            else {}
        )
        after = {row.port: row.state for row in run.tcp_port_results}
        changes = [
            {
                "port": port,
                "previous": before[port],
                "current": after[port],
                "kind": "inconclusive"
                if "unknown" in (before[port], after[port])
                else "state_changed",
            }
            for port in sorted(before.keys() & after.keys())
            if before[port] != after[port]
        ]
        items.append(
            {
                "report": report_from_run(run).to_dict(),
                "baseline_id": str(previous.id) if previous else None,
                "configuration_changed": previous.configuration != run.configuration
                if previous
                else False,
                "changes": changes,
                "only_in_previous": sorted(before.keys() - after.keys()),
                "only_in_current": sorted(after.keys() - before.keys()),
            }
        )
        previous = run
    return {"target": target, "items": items, "next_cursor": cursor}
