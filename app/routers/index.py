from flask import Blueprint
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db

index_bp = Blueprint("index", __name__)


@index_bp.route("/")
def index():
    try:
        db.session.execute(select(1))
    except SQLAlchemyError:
        db.session.rollback()
        return {"status": "unavailable"}, 503
    return {"status": "ok"}, 200
