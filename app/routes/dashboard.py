from flask import Blueprint, render_template


dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.get("/")
def index():
    return render_template("dashboard.html")


@dashboard_bp.get("/health")
def health():
    return {"status": "ok", "application": "RosterFlow"}, 200
