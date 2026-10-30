import json
from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

import pytest
from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    Uuid,
    create_engine,
    select,
)

from engine.report import ScanConfiguration, ScanReport
from engine.services.tcp import PortState, TCPPortResult


@pytest.fixture
def report():
    return ScanReport(
        target="127.0.0.1",
        configuration=ScanConfiguration((22, 80, 443), ("127.0.0.1",), 1, 20, 100),
        started_at=datetime(2026, 10, 30, 10, tzinfo=UTC),
        completed_at=datetime(2026, 10, 30, 10, 0, 1, tzinfo=UTC),
        results={
            "tcp": [
                TCPPortResult("127.0.0.1", 22, PortState.OPEN, "Connection accepted"),
                TCPPortResult(
                    "127.0.0.1", 80, PortState.CLOSED, "Connection refused", 111
                ),
                TCPPortResult(
                    "127.0.0.1", 443, PortState.UNKNOWN, "Connection timed out"
                ),
            ]
        },
    )


def test_json_report_contains_evidence_configuration_and_summary(report):
    payload = json.loads(report.to_json())
    assert UUID(payload["id"]) == report.id
    assert payload["schema_version"] == 1
    assert payload["started_at"] == "2026-10-30T10:00:00+00:00"
    assert payload["completed_at"] == "2026-10-30T10:00:01+00:00"
    assert payload["configuration"] == {
        "ports": [22, 80, 443],
        "allowed_targets": ["127.0.0.1"],
        "timeout": 1,
        "concurrency": 20,
        "rate_limit": 100,
    }
    assert payload["results"]["tcp"][1] == {
        "target": "127.0.0.1",
        "port": 80,
        "state": "closed",
        "evidence": "Connection refused",
        "error_number": 111,
    }
    assert payload["summary"] == {
        "tcp": {"total": 3, "open": 1, "closed": 1, "unknown": 1}
    }


def test_database_record_retains_native_types_and_detached_json_payloads(report):
    record = report.to_record()
    assert record["id"] is report.id
    assert isinstance(record["id"], UUID)
    assert record["started_at"] is report.started_at
    assert record["completed_at"] is report.completed_at
    assert "summary" not in record
    assert json.loads(json.dumps(record["configuration"])) == record["configuration"]
    assert json.loads(json.dumps(record["results"])) == record["results"]
    record["results"]["tcp"][0]["evidence"] = "modified copy"
    assert report.results["tcp"][0].evidence == "Connection accepted"


def test_report_ids_are_unique_and_summary_handles_empty_results(report):
    other = ScanReport(
        target=report.target,
        configuration=report.configuration,
        started_at=report.started_at,
        completed_at=report.completed_at,
        results={"tcp": []},
    )
    assert other.id != report.id
    assert other.summary == {"tcp": {"total": 0, "open": 0, "closed": 0, "unknown": 0}}


@pytest.mark.parametrize("field", ["started_at", "completed_at"])
def test_naive_timestamps_are_rejected(report, field):
    data = {
        "target": report.target,
        "configuration": report.configuration,
        "started_at": report.started_at,
        "completed_at": report.completed_at,
        "results": {},
    }
    data[field] = report.started_at.replace(tzinfo=None)
    with pytest.raises(ValueError, match="timezone-aware"):
        ScanReport(**data)


def test_completion_before_start_is_rejected(report):
    with pytest.raises(ValueError, match="precede"):
        ScanReport(
            target=report.target,
            configuration=report.configuration,
            started_at=report.completed_at,
            completed_at=report.started_at,
            results={},
        )


def test_timezone_offsets_are_normalized_to_utc(report):
    offset = timezone(timedelta(hours=2))
    normalized = ScanReport(
        target=report.target,
        configuration=report.configuration,
        started_at=report.started_at.astimezone(offset),
        completed_at=report.completed_at.astimezone(offset),
        results={},
    )
    assert normalized.started_at.tzinfo is UTC
    assert normalized.completed_at.tzinfo is UTC
    assert normalized.to_dict()["started_at"] == report.to_dict()["started_at"]


def test_record_round_trips_through_sqlalchemy(report):
    metadata = MetaData()
    reports = Table(
        "scan_reports",
        metadata,
        Column("id", Uuid, primary_key=True),
        Column("schema_version", Integer, nullable=False),
        Column("target", String, nullable=False),
        Column("started_at", DateTime(timezone=True), nullable=False),
        Column("completed_at", DateTime(timezone=True), nullable=False),
        Column("configuration", JSON, nullable=False),
        Column("results", JSON, nullable=False),
    )
    database = create_engine("sqlite://")
    try:
        metadata.create_all(database)
        with database.begin() as connection:
            connection.execute(reports.insert().values(**report.to_record()))
            row = connection.execute(select(reports)).mappings().one()
        assert row["id"] == report.id
        assert row["target"] == report.target
        assert row["configuration"] == report.configuration.to_dict()
        assert row["results"] == report.to_record()["results"]
        # SQLite drops timezone information; PostgreSQL timestamptz preserves it.
        assert row["started_at"].replace(tzinfo=UTC) == report.started_at
        assert row["completed_at"].replace(tzinfo=UTC) == report.completed_at
    finally:
        database.dispose()
