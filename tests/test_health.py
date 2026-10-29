from sqlalchemy.exc import OperationalError

from app.extensions import db


def test_health_check_reports_ready(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_health_check_reports_database_failure(client, monkeypatch):
    def fail(*args, **kwargs):
        raise OperationalError("SELECT 1", {}, Exception("database unavailable"))

    monkeypatch.setattr(db.session, "execute", fail)

    response = client.get("/")

    assert response.status_code == 503
    assert response.get_json() == {"status": "unavailable"}
