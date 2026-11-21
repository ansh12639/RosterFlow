from flask import Flask, app, render_template
from dotenv import load_dotenv  # type: ignore

from .config import Config
from .extensions import db, migrate


def create_app(config_class=Config):
    load_dotenv()
    app = Flask(__name__)
    app.config.from_object(config_class)

    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        raise RuntimeError(
            "DATABASE_URL is missing. Copy .env.example to .env and configure MySQL."
        )

    db.init_app(app)
    migrate.init_app(app, db)

    # Import models so Flask-Migrate can discover their metadata.
    from . import models  # noqa: F401

    from .routes.dashboard import dashboard_bp

    app.register_blueprint(dashboard_bp)

    from .routes.employees import employees_bp

    app.register_blueprint(employees_bp)

    from .routes.catalog import catalog_bp

    app.register_blueprint(catalog_bp)

    from .routes.pods import pods_bp

    app.register_blueprint(pods_bp)

    from .routes.working_rules import working_rules_bp

    app.register_blueprint(working_rules_bp)

    from .routes.availability import availability_bp

    app.register_blueprint(availability_bp)

    from .routes.weekly_offs import weekly_offs_bp

    app.register_blueprint(weekly_offs_bp)

    from .routes.holidays import holidays_bp

    app.register_blueprint(holidays_bp)

    from .routes.rosters import rosters_bp

    app.register_blueprint(rosters_bp)

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("errors/404.html"), 404

    return app
