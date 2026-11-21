from datetime import date

import click
from flask import Flask, render_template, request
from sqlalchemy import event
from sqlalchemy.engine import Engine

from .config import Config
from .extensions import csrf, db, migrate


@event.listens_for(Engine, "connect")
def _sqlite_foreign_keys(dbapi_connection, _record):
    # SQLite ignores ON DELETE CASCADE unless foreign keys are switched on.
    if dbapi_connection.__class__.__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        raise RuntimeError("DATABASE_URL is missing. Copy .env.example to .env and configure MySQL.")

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    from . import models  # noqa: F401  (register metadata)
    from .routes.availability import availability_bp
    from .routes.catalog import catalog_bp
    from .routes.dashboard import dashboard_bp
    from .routes.employees import employees_bp
    from .routes.holidays import holidays_bp
    from .routes.pods import pods_bp
    from .routes.rosters import rosters_bp
    from .routes.weekly_offs import weekly_offs_bp
    from .routes.working_rules import working_rules_bp

    for bp in (dashboard_bp, employees_bp, catalog_bp, pods_bp, working_rules_bp, availability_bp,
               weekly_offs_bp, holidays_bp, rosters_bp):
        app.register_blueprint(bp)

    @app.context_processor
    def inject_globals():
        return {"endpoint": request.endpoint or "", "today": date.today()}

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("errors/404.html"), 404

    _register_cli(app)

    if app.config.get("AUTO_SEED"):
        with app.app_context():
            _auto_seed()
    return app


def _auto_seed():
    from .models import Employee
    from .seed import seed_demo

    db.create_all()
    if Employee.query.count() == 0:
        seed_demo()


def _register_cli(app):
    @app.cli.command("init-db")
    def init_db():
        """Create all tables (safe to re-run)."""
        db.create_all()
        click.echo("Tables created.")

    @app.cli.command("seed-demo")
    @click.option("--no-generate", is_flag=True, help="Skip generating demo rosters.")
    def seed_demo_cmd(no_generate):
        """DROP all tables, recreate them and load the demo dataset."""
        from .seed import seed_demo

        db.drop_all()
        db.create_all()
        summary = seed_demo(generate=not no_generate)
        click.echo(f"Seeded: {summary}")

    @app.cli.command("generate-roster")
    @click.argument("year", type=int)
    @click.argument("month", type=int)
    def generate_cmd(year, month):
        """Generate a roster version for YEAR MONTH."""
        from .scheduling.service import conflict_counts, generate_roster

        version = generate_roster(year, month)
        click.echo(f"Created {version.label}: {conflict_counts(version.id)}")
