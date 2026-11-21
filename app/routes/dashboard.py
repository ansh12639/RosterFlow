from datetime import date

from flask import Blueprint, abort, current_app, flash, redirect, render_template, url_for

from app.extensions import db
from app.models import (Assignment, Availability, Brand, Employee, Pod, Process, RosterVersion)
from app.scheduling import service

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.get("/")
def index():
    today = date.today()
    brands = Brand.query.filter_by(active=True).all()
    primaries = {}
    for a in Assignment.query.filter_by(active=True, priority=1).all():
        primaries.setdefault(a.brand_id, set()).add(a.employee_id)
    single = sum(1 for b in brands if len(primaries.get(b.id, ())) == 1)
    multi = sum(1 for b in brands if len(primaries.get(b.id, ())) > 1)
    stats = dict(
        employees=Employee.query.filter_by(active=True).count(),
        brands=len(brands), single=single, multi=multi,
        single_pct=round(100 * single / len(brands)) if brands else 0,
        pods=Pod.query.count(), processes=Process.query.filter_by(active=True).count(),
        pending_leave=Availability.query.filter_by(approval_status="PENDING").count(),
    )
    versions = (RosterVersion.query.filter(RosterVersion.status != "ARCHIVED")
                .order_by(RosterVersion.roster_month.desc(), RosterVersion.version_number.desc()).limit(6).all())
    counts = {v.id: service.conflict_counts(v.id) for v in versions}

    today_info, current = None, service.latest_version_for(today)
    if current:
        from app.scheduling.views import RosterView
        rv = RosterView(current)
        if rv.days[0] <= today <= rv.days[-1]:
            today_info = rv.day_detail(today)
    pending = (Availability.query.filter_by(approval_status="PENDING")
               .order_by(Availability.start_date).limit(5).all())
    return render_template("dashboard.html", stats=stats, versions=versions, counts=counts,
                           current=current, today_info=today_info, pending=pending)


@dashboard_bp.get("/health")
def health():
    try:
        db.session.execute(db.text("SELECT 1"))
        database = "ok"
    except Exception:  # pragma: no cover
        database = "unavailable"
    return {"status": "ok", "application": "RosterFlow", "database": database}, 200


@dashboard_bp.post("/demo/reset")
def reset_demo():
    if not current_app.config.get("ALLOW_DEMO_RESET"):
        abort(403)
    from app.seed import seed_demo

    db.session.remove()
    db.drop_all()
    db.create_all()
    summary = seed_demo()
    flash(f"Demo data reset: {summary['employees']} employees, {summary['brands']} brands, "
          f"{summary['pods']} pods. Rosters for this month (published) and next month (draft) regenerated.", "success")
    return redirect(url_for("dashboard.index"))
