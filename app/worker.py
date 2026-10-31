"""Process API scan jobs outside HTTP requests, using PostgreSQL as the queue."""

import asyncio
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from threading import Lock
from uuid import UUID

import click
from flask import Flask, current_app
from sqlalchemy import select, text, update

from app.extensions import db
from app.models import ScanJob, User
from app.services.reports import store_report
from app.services.scans import validate_scan
from engine.report import ScanReport
from engine.services import ScannerService
from engine.services.tcp import TCPPortScanner

# SQLite supports one test/development worker process. PostgreSQL coordinates
# processes with a session lock without holding a write transaction during scans.
_sqlite_worker_lock = Lock()


@contextmanager
def worker_lock() -> Iterator[bool]:
    if db.engine.dialect.name == "postgresql":
        with db.engine.connect().execution_options(
            isolation_level="AUTOCOMMIT"
        ) as connection:
            acquired = connection.scalar(text("SELECT pg_try_advisory_lock(67204201)"))
            try:
                yield acquired
            finally:
                if acquired:
                    connection.execute(text("SELECT pg_advisory_unlock(67204201)"))
    else:
        acquired = _sqlite_worker_lock.acquire(blocking=False)
        try:
            yield acquired
        finally:
            if acquired:
                _sqlite_worker_lock.release()


async def execute_scan(
    job_id: UUID, target: str, config: dict[str, object]
) -> ScanReport:
    scanner = TCPPortScanner(
        timeout=config["timeout"],
        concurrency=config["concurrency"],
        rate_limit=config["rate_limit"],
    )
    async with asyncio.timeout(current_app.config["SCAN_JOB_TIMEOUT"]):
        return await ScannerService(scanner).run_all(
            target, config["ports"], allowed_targets=[target], report_id=job_id
        )


def fail_job(job_id: UUID, message: str) -> None:
    db.session.rollback()
    job = db.session.get(ScanJob, job_id)
    job.status = "failed"
    job.error = message
    job.completed_at = datetime.now(UTC)
    db.session.commit()


def work_once() -> bool:
    """Run at most one pending scan; return False when idle or another worker is busy."""
    with worker_lock() as acquired:
        if not acquired:
            return False
        # A live worker holds the global lock; remaining running jobs were interrupted.
        db.session.execute(
            update(ScanJob)
            .where(ScanJob.status == "running")
            .values(
                status="failed",
                error="Worker stopped before scan completion",
                completed_at=datetime.now(UTC),
            )
        )
        job = db.session.scalar(
            select(ScanJob)
            .where(ScanJob.status == "queued")
            .order_by(ScanJob.created_at, ScanJob.id)
            .limit(1)
        )
        if job is None:
            db.session.commit()
            return False
        job_id, owner_id, target, config = (
            job.id,
            job.user_id,
            job.target,
            job.configuration,
        )
        if not db.session.get(User, owner_id).is_active:
            fail_job(job_id, "Scan owner is disabled")
            return True
        job.status = "running"
        job.started_at = datetime.now(UTC)
        db.session.commit()
        db.session.remove()
        try:
            target, config = validate_scan(
                {
                    "target": target,
                    "ports": config["ports"],
                    "timeout": config["timeout"],
                    "concurrency": config["concurrency"],
                    "rate_limit": config["rate_limit"],
                }
            )
            report = asyncio.run(execute_scan(job_id, target, config))
            # Report rows and job completion form one atomic transaction.
            job = db.session.get(ScanJob, job_id)
            if job.status != "running":
                raise RuntimeError("Job no longer running")
            store_report(report, owner_id)
            job.status = "completed"
            job.report_id = report.id
            job.completed_at = datetime.now(UTC)
            db.session.commit()
        except KeyboardInterrupt:
            fail_job(job_id, "Worker interrupted during scan")
            raise
        except TimeoutError:
            fail_job(job_id, "Scan exceeded the server time limit")
        except Exception:
            current_app.logger.exception("Scan job failed: %s", job_id)
            fail_job(job_id, "Scan or report storage failed; check server logs")
        finally:
            db.session.remove()
        return True


def register_worker(app: Flask) -> None:
    @app.cli.command("scan-worker")
    @click.option(
        "--once", is_flag=True, help="Process at most one queued scan and exit."
    )
    def scan_worker(once: bool) -> None:
        """Run the API's scan worker in a separate process."""
        while True:
            try:
                worked = work_once()
            finally:
                db.session.remove()
            if once:
                return
            if not worked:
                time.sleep(1)
