from flask import Flask

# Import models so Flask-Migrate sees them in db.metadata.
from . import models as models
from .config import Config
from .extensions import register_extensions
from .routers import register_blueprints


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config())

    register_extensions(app)
    register_blueprints(app)

    return app
