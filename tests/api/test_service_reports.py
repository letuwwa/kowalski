from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from werkzeug.exceptions import BadRequest

from api import worker
from api.extensions import db
from api.models import ScanJob, ScanRun, User
from api.services.reports import report_from_run, store_report
from api.services.scans import history, service_changes, validate_scan
from core.report import ScanConfiguration, ScanReport, ServiceObservation
from core.services import ScannerService
from core.services.tcp import PortState, TCPPortResult


@pytest.mark.parametrize("ports", [None, "22", [0], [True], [65536]])
def test_api_rejects_invalid_service_ports(app, ports):
    with pytest.raises(BadRequest):
        validate_scan({"target": "127.0.0.1", "ports": [22], "service_ports": ports})


def test_api_worker_persistence_and_chronological_service_changes(app, monkeypatch):
    owner = User(
        email="services@example.test",
        username="services",
        first_name="Test",
        last_name="User",
        password_hash="unused",
    )
    db.session.add(owner)
    db.session.commit()
    owner_id = owner.id
    now = datetime.now(UTC)
    observation = ServiceObservation(
        "127.0.0.1",
        2222,
        "identified",
        "U1NILTIuMC1UZXN0XzENCg==",
        protocol="ssh",
        banner="SSH-2.0-Test_1",
        protocol_version="2.0",
        advertised_software="Test_1",
        confidence="high",
    )
    reports = []
    for index, row in enumerate(
        (
            observation,
            replace(observation, banner="SSH-2.0-Test_2", advertised_software="Test_2"),
            replace(
                observation,
                status="timeout",
                protocol=None,
                confidence=None,
                banner=None,
            ),
        )
    ):
        report = ScanReport(
            target="127.0.0.1",
            configuration=ScanConfiguration(
                (2222,), ("127.0.0.1",), 1, 20, 100, (2222,)
            ),
            started_at=now + timedelta(seconds=index),
            completed_at=now + timedelta(seconds=index),
            results={
                "tcp": [TCPPortResult("127.0.0.1", 2222, PortState.OPEN, "Accepted")]
            },
            services=[row],
        )
        stored = store_report(report, owner_id)
        db.session.commit()
        assert report_from_run(stored).to_dict() == report.to_dict()
        assert store_report(report, owner_id).id == report.id
        reports.append(stored)
    items = history(owner_id, "127.0.0.1", {})["items"]
    assert items[0]["service_changes"] == []
    assert items[1]["service_changes"][0]["kind"] == "banner_changed"
    assert items[2]["service_changes"][0]["kind"] == "inconclusive"
    assert items[2]["changes"] == []
    assert service_changes(SimpleNamespace(services=[]), reports[0]) == []
    assert service_changes(reports[0], SimpleNamespace(services=[])) == []
    target, config = validate_scan(
        {"target": "127.0.0.1", "ports": [2222], "service_ports": [2222]}
    )
    job = ScanJob(user_id=owner_id, target=target, configuration=config)
    db.session.add(job)
    db.session.commit()
    job_id = job.id
    captured = []

    async def run_all(self, target, ports, **kwargs):
        captured.append(kwargs["service_ports"])
        return replace_report(kwargs["report_id"])

    def replace_report(identifier):
        return ScanReport(
            id=identifier,
            target=target,
            configuration=ScanConfiguration((2222,), (target,), 1, 20, 100, (2222,)),
            started_at=now,
            completed_at=now,
            results={"tcp": [TCPPortResult(target, 2222, PortState.OPEN, "Accepted")]},
            services=[observation],
        )

    monkeypatch.setattr(ScannerService, "run_all", run_all)
    assert worker.work_once()
    assert captured == [[2222]]
    assert db.session.get(ScanJob, job_id).status == "completed"
    assert db.session.get(ScanRun, job_id).services[0]["protocol"] == "ssh"
