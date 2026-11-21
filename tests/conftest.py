import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from app.config import TestConfig  # noqa: E402
from app.extensions import db  # noqa: E402

DEMO_TODAY = date(2026, 11, 21)  # current month Nov 2026 (published), next Dec 2026 (draft)


@pytest.fixture()
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def seeded(app):
    from app.seed import seed_demo

    seed_demo(today=DEMO_TODAY)
    return app


@pytest.fixture()
def client(app):
    return app.test_client()
