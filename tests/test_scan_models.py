import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import ScanRun, TCPPortResult, User
from engine.report import ScanConfiguration, ScanReport
from engine.services.tcp import PortState
from engine.services.tcp import TCPPortResult as EnginePortResult


@pytest.fixture
def owner(app):
    user = User(
        email="scanner@example.test",
        username="scanner",
        first_name="Scan",
        last_name="Owner",
        password_hash="unused-in-model-tests",
    )
    db.session.add(user)
    db.session.commit()
    return user


def make_run(owner, **overrides):
    started_at = datetime.now(UTC)
    values = {
        "id": uuid.uuid4(),
        "user": owner,
        "target": "127.0.0.1",
        "started_at": started_at,
        "completed_at": started_at + timedelta(seconds=1),
        "configuration": {
            "ports": [22],
            "allowed_targets": ["127.0.0.1"],
            "timeout": 1.0,
            "concurrency": 20,
            "rate_limit": 100.0,
        },
        "schema_version": 1,
    }
    values.update(overrides)
    return ScanRun(**values)


@pytest.fixture
def scan_run(owner):
    scan = make_run(owner)
    db.session.add(scan)
    db.session.commit()
    return scan


def test_report_uuid_configuration_evidence_and_relationships_round_trip(owner):
    started_at = datetime.now(UTC)
    report = ScanReport(
        target="127.0.0.1",
        configuration=ScanConfiguration((22, 443), ("127.0.0.1",), 0.5, 2, 10),
        started_at=started_at,
        completed_at=started_at + timedelta(seconds=1),
        results={
            "tcp": [
                EnginePortResult(
                    "127.0.0.1", 22, PortState.OPEN, "Connection accepted"
                ),
                EnginePortResult(
                    "127.0.0.1", 443, PortState.UNKNOWN, "Network unreachable", 101
                ),
            ]
        },
    )
    scan = ScanRun(
        id=report.id,
        user=owner,
        target=report.target,
        started_at=report.started_at,
        completed_at=report.completed_at,
        configuration=report.configuration.to_dict(),
        schema_version=1,
        tcp_port_results=[
            TCPPortResult(
                port=result.port,
                state=result.state.value,
                evidence=result.evidence,
                error_number=result.error_number,
            )
            for result in reversed(report.results["tcp"])
        ],
    )
    db.session.add(scan)
    db.session.commit()
    db.session.expire_all()

    stored = db.session.get(ScanRun, report.id)
    assert stored.id == report.id
    assert stored.user == owner
    assert owner.scan_runs == [stored]
    assert stored.target == report.target
    assert stored.schema_version == 1
    assert stored.configuration == report.configuration.to_dict()
    assert [result.port for result in stored.tcp_port_results] == [22, 443]
    assert stored.tcp_port_results[1].evidence == "Network unreachable"
    assert stored.tcp_port_results[1].error_number == 101
    assert stored.tcp_port_results[0].error_number is None
    assert stored.tcp_port_results[0].scan_run is stored
    assert stored.created_at is not None
    for stored_time, report_time in (
        (stored.started_at, report.started_at),
        (stored.completed_at, report.completed_at),
    ):
        # SQLite drops timezone information; PostgreSQL may return a local offset.
        if stored_time.tzinfo is None:
            stored_time = stored_time.replace(tzinfo=UTC)
        assert stored_time == report_time


@pytest.mark.parametrize(
    "field", ["target", "started_at", "completed_at", "configuration", "schema_version"]
)
def test_scan_required_fields(owner, field):
    db.session.add(make_run(owner, **{field: None}))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


@pytest.mark.parametrize("version", [0, -1])
def test_schema_version_must_be_positive(owner, version):
    db.session.add(make_run(owner, schema_version=version))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_scan_completion_cannot_precede_start(owner):
    scan = make_run(owner)
    scan.completed_at = scan.started_at - timedelta(seconds=1)
    db.session.add(scan)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


@pytest.mark.parametrize("user_id", [None, uuid.uuid4()])
def test_scan_requires_existing_owner(app, user_id):
    scan = make_run(None)
    scan.user_id = user_id
    db.session.add(scan)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


@pytest.mark.parametrize("scan_id", [None, uuid.uuid4()])
def test_result_requires_existing_scan(app, scan_id):
    db.session.add(
        TCPPortResult(scan_id=scan_id, port=22, state="open", evidence="Accepted")
    )
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


@pytest.mark.parametrize("port", [0, -1, 65536, None])
def test_invalid_ports_are_rejected(scan_run, port):
    db.session.add(
        TCPPortResult(scan_run=scan_run, port=port, state="open", evidence="Accepted")
    )
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


@pytest.mark.parametrize("state", ["bad", "OPEN", "", None])
def test_invalid_states_are_rejected(scan_run, state):
    db.session.add(
        TCPPortResult(scan_run=scan_run, port=22, state=state, evidence="Evidence")
    )
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


@pytest.mark.parametrize("port", [1, 65535])
@pytest.mark.parametrize("state", ["open", "closed", "unknown"])
def test_supported_states_and_boundary_ports_are_stored(scan_run, port, state):
    result = TCPPortResult(
        scan_run=scan_run, port=port, state=state, evidence="Evidence"
    )
    db.session.add(result)
    db.session.commit()
    assert result.state == state
    assert result.port == port


def test_result_requires_evidence(scan_run):
    db.session.add(TCPPortResult(scan_run=scan_run, port=22, state="open"))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_duplicate_ports_are_rejected_and_same_port_in_later_run_is_allowed(scan_run):
    first = TCPPortResult(scan_run=scan_run, port=22, state="open", evidence="Accepted")
    db.session.add(first)
    db.session.commit()
    scan_id = scan_run.id
    db.session.add(
        TCPPortResult(scan_id=scan_id, port=22, state="closed", evidence="Refused")
    )
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()
    assert len(scan_run.tcp_port_results) == 1

    later = make_run(scan_run.user)
    later.tcp_port_results.append(
        TCPPortResult(port=22, state="closed", evidence="Refused")
    )
    db.session.add(later)
    db.session.commit()
    assert later.id != scan_id
    assert len(db.session.scalars(select(TCPPortResult)).all()) == 2


def test_duplicate_report_uuid_is_rejected(scan_run):
    with pytest.raises(IntegrityError):
        db.session.execute(
            ScanRun.__table__.insert().values(
                id=scan_run.id,
                user_id=scan_run.user_id,
                target="127.0.0.1",
                started_at=scan_run.started_at,
                completed_at=scan_run.completed_at,
                configuration={},
                schema_version=1,
            )
        )
    db.session.rollback()


@pytest.mark.parametrize("bulk_delete", [False, True])
def test_deleting_scan_removes_results_but_preserves_owner(scan_run, bulk_delete):
    result = TCPPortResult(
        scan_run=scan_run, port=22, state="open", evidence="Accepted"
    )
    db.session.add(result)
    db.session.commit()
    result_id, scan_id, owner_id = result.id, scan_run.id, scan_run.user_id
    db.session.expire_all()
    if bulk_delete:
        db.session.execute(delete(ScanRun).where(ScanRun.id == scan_id))
    else:
        assert len(scan_run.tcp_port_results) == 1
        db.session.delete(scan_run)
    db.session.commit()
    db.session.expunge_all()
    assert db.session.get(TCPPortResult, result_id) is None
    assert db.session.get(ScanRun, scan_id) is None
    assert db.session.get(User, owner_id) is not None


@pytest.mark.parametrize("load_history", [False, True])
def test_deleting_owner_with_history_is_restricted(scan_run, load_history):
    owner = scan_run.user
    if load_history:
        assert owner.scan_runs == [scan_run]
    db.session.delete(owner)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()
    assert db.session.get(ScanRun, scan_run.id) is not None


def test_failed_result_insert_rolls_back_entire_run(owner):
    scan = make_run(owner)
    scan_id = scan.id
    scan.tcp_port_results.append(
        TCPPortResult(port=0, state="open", evidence="Invalid")
    )
    db.session.add(scan)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()
    assert db.session.get(ScanRun, scan_id) is None
