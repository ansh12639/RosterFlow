import os

from dotenv import load_dotenv

load_dotenv()


def _database_url():
    url = os.getenv("DATABASE_URL", "").strip()
    # Some hosts hand out mysql:// URLs; SQLAlchemy needs the driver name.
    if url.startswith("mysql://"):
        url = "mysql+pymysql://" + url[len("mysql://"):]
    return url or None


def _engine_options():
    options = {"pool_pre_ping": True, "pool_recycle": 280}
    # Hosted MySQL (Aiven, TiDB Cloud, Azure…) requires TLS: point MYSQL_SSL_CA at a CA bundle.
    ca = os.getenv("MYSQL_SSL_CA")
    if ca:
        options["connect_args"] = {"ssl": {"ca": ca}}
    return options


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = _engine_options()

    # Scheduling policy (documented assumptions, configurable per deployment)
    MAX_SHIFT_SPAN_HOURS = float(os.getenv("MAX_SHIFT_SPAN_HOURS", "9"))
    MAX_COVERS_PER_DAY = int(os.getenv("MAX_COVERS_PER_DAY", "1"))

    # Optional AI explanations (falls back to a deterministic explanation)
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    AI_MODEL = os.getenv("AI_MODEL", "claude-opus-5-5")

    # Seed the demo dataset automatically on first start when the DB is empty.
    AUTO_SEED = os.getenv("AUTO_SEED", "0") == "1"
    # Allow the "Reset demo data" button (keep enabled on the public demo).
    ALLOW_DEMO_RESET = os.getenv("ALLOW_DEMO_RESET", "1") == "1"


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    WTF_CSRF_ENABLED = False
    ANTHROPIC_API_KEY = None
    AUTO_SEED = False
