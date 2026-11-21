"""WSGI entry point: `gunicorn run:app` (production) or `python run.py` (development)."""
import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "1") == "1")
