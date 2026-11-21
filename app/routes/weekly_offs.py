from datetime import date

from flask import Blueprint, render_template, request, redirect, url_for, flash
from sqlalchemy import or_

from app.extensions import db
from app.models import Employee, EmployeeWeeklyOff

weekly_offs_bp = Blueprint("weekly_offs", __name__, url_prefix="/weekly-offs")

WEEKDAYS = {
    0: "Monday",
    1: "Tuesday",
    2: "Wednesday",
    3: "Thursday",
    4: "Friday",
    5: "Saturday",
    6: "Sunday",
}


@weekly_offs_bp.get("/")
def index():
    employees = Employee.query.filter_by(active=True).order_by(Employee.full_name).all()

    records = EmployeeWeeklyOff.query.order_by(
        EmployeeWeeklyOff.effective_from.desc()
    ).all()

    return render_template(
        "weekly_offs.html",
        employees=employees,
        records=records,
        weekdays=WEEKDAYS,
        today=date.today(),
    )


@weekly_offs_bp.post("/add")
def add_weekly_off():
    employee_id = request.form.get("employee_id", type=int)
    weekday = request.form.get("weekday", type=int)

    start_raw = request.form.get("effective_from", "").strip()
    end_raw = request.form.get("effective_to", "").strip()

    employee = db.session.get(Employee, employee_id) if employee_id else None

    if not employee or not employee.active:
        flash("Select a valid active employee.", "error")
        return redirect(url_for("weekly_offs.index"))

    if weekday not in WEEKDAYS:
        flash("Select a valid weekday.", "error")
        return redirect(url_for("weekly_offs.index"))

    try:
        effective_from = date.fromisoformat(start_raw)
        effective_to = date.fromisoformat(end_raw) if end_raw else None
    except ValueError:
        flash("Enter valid effective dates.", "error")
        return redirect(url_for("weekly_offs.index"))

    if effective_to and effective_to < effective_from:
        flash("End date cannot be earlier than start date.", "error")
        return redirect(url_for("weekly_offs.index"))

    overlap_filters = [
        EmployeeWeeklyOff.employee_id == employee.id,
        EmployeeWeeklyOff.weekday == weekday,
        or_(
            EmployeeWeeklyOff.effective_to.is_(None),
            EmployeeWeeklyOff.effective_to >= effective_from,
        ),
    ]

    if effective_to is not None:
        overlap_filters.append(EmployeeWeeklyOff.effective_from <= effective_to)

    existing = EmployeeWeeklyOff.query.filter(*overlap_filters).first()

    if existing:
        flash(
            "This employee already has an overlapping weekly-off "
            "schedule for this weekday.",
            "error",
        )
        return redirect(url_for("weekly_offs.index"))

    record = EmployeeWeeklyOff(
        employee_id=employee.id,
        weekday=weekday,
        effective_from=effective_from,
        effective_to=effective_to,
    )

    db.session.add(record)
    db.session.commit()

    flash(
        f"{WEEKDAYS[weekday]} weekly off assigned to {employee.full_name}.",
        "success",
    )

    return redirect(url_for("weekly_offs.index"))


@weekly_offs_bp.post("/<int:record_id>/close")
def close_weekly_off(record_id):
    record = db.get_or_404(EmployeeWeeklyOff, record_id)

    end_raw = request.form.get("effective_to", "").strip()

    try:
        effective_to = date.fromisoformat(end_raw)
    except ValueError:
        flash("Enter a valid end date.", "error")
        return redirect(url_for("weekly_offs.index"))

    if effective_to < record.effective_from:
        flash("End date cannot be earlier than start date.", "error")
        return redirect(url_for("weekly_offs.index"))

    record.effective_to = effective_to
    db.session.commit()

    flash("Weekly-off schedule closed successfully.", "success")
    return redirect(url_for("weekly_offs.index"))
