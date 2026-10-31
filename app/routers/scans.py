"""Authenticated API scans, reports, and chronological history."""

from uuid import UUID

from flask import Blueprint, Response, current_app, request, url_for
from flask.typing import ResponseReturnValue
from flask_jwt_extended import current_user, jwt_required
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException, abort

from app.extensions import db, limiter
from app.models import ScanJob, ScanRun
from app.routers.utils import json_body
from app.services.reports import report_from_run
from app.services.scans import history, ipv4, job_dict, paginate, submit_scan

scans_bp = Blueprint("scans", __name__, url_prefix="/scans")


@scans_bp.before_request
@jwt_required()
def require_scan_user() -> None:
    if current_user is None:
        abort(401, description="User not found")
    if not current_user.is_active:
        abort(403, description="User account is disabled")


@scans_bp.errorhandler(HTTPException)
def handle_scan_request_error(error: HTTPException) -> ResponseReturnValue:
    db.session.rollback()
    return {"message": error.description}, error.code


@scans_bp.errorhandler(SQLAlchemyError)
def handle_scan_database_error(error: SQLAlchemyError) -> ResponseReturnValue:
    db.session.rollback()
    current_app.logger.exception("Scan database operation failed")
    return {"message": "Scan storage is unavailable"}, 503


@scans_bp.after_request
def protect_scan_response(response: Response) -> Response:
    response.headers["Cache-Control"] = "no-store"
    return response


@scans_bp.post("", strict_slashes=False)
@limiter.limit("10 per minute")
def create_scan() -> ResponseReturnValue:
    job = submit_scan(json_body(), current_user.id)
    return job_dict(job), 202, {"Location": url_for("scans.get_scan", scan_id=job.id)}


@scans_bp.get("", strict_slashes=False)
def list_scans() -> ResponseReturnValue:
    query = select(ScanJob).where(ScanJob.user_id == current_user.id)
    if "target" in request.args:
        query = query.where(ScanJob.target == ipv4(request.args["target"]))
    if status := request.args.get("status"):
        if status not in {"queued", "running", "completed", "failed"}:
            abort(400, description="Invalid scan status")
        query = query.where(ScanJob.status == status)
    jobs, cursor = paginate(query, ScanJob, ScanJob.created_at, request.args)
    return {"items": [job_dict(job) for job in jobs], "next_cursor": cursor}


@scans_bp.get("/history")
def scan_history() -> ResponseReturnValue:
    target = ipv4(request.args.get("target"))
    return history(current_user.id, target, request.args)


@scans_bp.get("/<scan_id>")
def get_scan(scan_id: str) -> ResponseReturnValue:
    try:
        identifier = UUID(scan_id)
    except ValueError:
        abort(400, description="Invalid scan ID")
    job = db.session.scalar(
        select(ScanJob).where(
            ScanJob.id == identifier, ScanJob.user_id == current_user.id
        )
    )
    if job is None:
        abort(404, description="Scan not found")
    response = job_dict(job)
    response["report"] = None
    if job.status == "completed":
        run = db.session.scalar(
            select(ScanRun).where(
                ScanRun.id == job.report_id, ScanRun.user_id == current_user.id
            )
        )
        if run is None:
            abort(404, description="Report not found")
        response["report"] = report_from_run(run).to_dict()
    return response
