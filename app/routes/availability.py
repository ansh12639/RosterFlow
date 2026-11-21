from datetime import date

from flask import Blueprint, render_template, request, redirect, url_for, flash

from app.extensions import db
from app.models import Employee, Availability


availability_bp = Blueprint(
    "availability",
    __name__,
    url_prefix="/availability"
)

AVAILABILITY_TYPES = [
    "PLANNED_LEAVE",
    "COMP_OFF",
    "UNAVAILABLE",
]

APPROVAL_STATUSES = ["PENDING", "APPROVED", "REJECTED"]


@availability_bp.get("/")
def index():
    employees = (
        Employee.query
        .filter_by(active=True)
        .order_by(Employee.full_name)
        .all()
    )

    records = (
        Availability.query
        .order_by(Availability.start_date.desc())
        .all()
    )

    return render_template(
        "availability.html",
        employees=employees,
        records=records,
    )


@availability_bp.post("/add")
def add_availability():
    employee_id = request.form.get("employee_id", type=int)
    availability_type = request.form.get("availability_type", "").strip()
    start_raw = request.form.get("start_date", "").strip()
    end_raw = request.form.get("end_date", "").strip()
    notes = request.form.get("notes", "").strip()

    employee = db.session.get(Employee, employee_id) if employee_id else None

    if not employee or not employee.active:
        flash("Select a valid active employee.", "error")
        return redirect(url_for("availability.index"))

    if availability_type not in AVAILABILITY_TYPES:
        flash("Select a valid availability type.", "error")
        return redirect(url_for("availability.index"))

    try:
        start_date = date.fromisoformat(start_raw)
        end_date = date.fromisoformat(end_raw)
    except ValueError:
        flash("Enter valid start and end dates.", "error")
        return redirect(url_for("availability.index"))

    if end_date < start_date:
        flash("End date cannot be earlier than start date.", "error")
        return redirect(url_for("availability.index"))

    if len(notes) > 255:
        flash("Notes cannot exceed 255 characters.", "error")
        return redirect(url_for("availability.index"))

    # Check for overlapping pending or approved records
    # of the same employee and availability type.
    overlap = Availability.query.filter(
        Availability.employee_id == employee.id,
        Availability.availability_type == availability_type,
        Availability.approval_status.in_(["PENDING", "APPROVED"]),
        Availability.start_date <= end_date,
        Availability.end_date >= start_date,
    ).first()

    if overlap:
        flash(
            "An overlapping pending or approved availability record "
            "already exists for this employee and type.",
            "error",
        )
        return redirect(url_for("availability.index"))

    record = Availability(
        employee_id=employee.id,
        availability_type=availability_type,
        start_date=start_date,
        end_date=end_date,
        approval_status="PENDING",
        notes=notes or None,
    )

    db.session.add(record)
    db.session.commit()

    flash("Availability request submitted for approval.", "success")
    return redirect(url_for("availability.index"))


@availability_bp.post("/<int:record_id>/status")
def update_status(record_id):
    record = db.get_or_404(Availability, record_id)

    status = request.form.get("approval_status", "").strip().upper()

    if status not in APPROVAL_STATUSES:
        flash("Invalid approval status.", "error")
        return redirect(url_for("availability.index"))

    record.approval_status = status
    db.session.commit()

    flash(f"Availability request marked as {status}.", "success")
    return redirect(url_for("availability.index"))