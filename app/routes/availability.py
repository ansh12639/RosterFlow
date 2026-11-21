from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import Availability, Employee
from app.models.availability import AVAILABILITY_TYPES
from app.scheduling import service

availability_bp = Blueprint("availability", __name__, url_prefix="/availability")

APPROVAL_STATUSES = ["PENDING", "APPROVED", "REJECTED"]


@availability_bp.get("/")
def index():
    employees = Employee.query.filter_by(active=True).order_by(Employee.full_name).all()
    records = Availability.query.order_by(Availability.start_date.desc()).all()
    return render_template("availability.html", employees=employees, records=records, types=AVAILABILITY_TYPES)


@availability_bp.post("/add")
def add_availability():
    employee_id = request.form.get("employee_id", type=int)
    availability_type = request.form.get("availability_type", "").strip()
    notes = request.form.get("notes", "").strip()
    status = request.form.get("approval_status", "PENDING")
    employee = db.session.get(Employee, employee_id) if employee_id else None

    if not employee or not employee.active:
        flash("Select a valid active employee.", "error")
        return redirect(url_for("availability.index"))
    if availability_type not in AVAILABILITY_TYPES:
        flash("Select a valid availability type.", "error")
        return redirect(url_for("availability.index"))
    if status not in ("PENDING", "APPROVED"):
        status = "PENDING"
    try:
        start_date = date.fromisoformat(request.form.get("start_date", "").strip())
        end_date = date.fromisoformat(request.form.get("end_date", "").strip())
    except ValueError:
        flash("Enter valid start and end dates.", "error")
        return redirect(url_for("availability.index"))
    if end_date < start_date:
        flash("End date cannot be earlier than start date.", "error")
        return redirect(url_for("availability.index"))
    if len(notes) > 255:
        flash("Notes cannot exceed 255 characters.", "error")
        return redirect(url_for("availability.index"))

    overlap = Availability.query.filter(
        Availability.employee_id == employee.id,
        Availability.approval_status.in_(["PENDING", "APPROVED"]),
        Availability.start_date <= end_date,
        Availability.end_date >= start_date,
    ).first()
    if overlap:
        flash("This employee already has a pending or approved absence overlapping those dates.", "error")
        return redirect(url_for("availability.index"))

    record = Availability(employee_id=employee.id, availability_type=availability_type, start_date=start_date,
                          end_date=end_date, approval_status=status, notes=notes or None)
    db.session.add(record)
    db.session.commit()
    if status == "APPROVED":
        return _after_approval(record)
    flash("Request recorded as PENDING. Check its roster impact before approving.", "success")
    return redirect(url_for("availability.index"))


def _after_approval(record):
    if service.latest_version_for(record.start_date):
        flash(f"Approved. Here is the impact on the existing roster for {record.employee.full_name} – "
              "apply it to the roster to update coverage.", "success")
        return redirect(url_for("rosters.impact", availability_id=record.id))
    flash("Approved. It will be applied automatically when that month's roster is generated.", "success")
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
    if status == "APPROVED":
        return _after_approval(record)
    flash(f"Request marked as {status}.", "success")
    return redirect(url_for("availability.index"))


@availability_bp.post("/<int:record_id>/delete")
def delete(record_id):
    record = db.get_or_404(Availability, record_id)
    db.session.delete(record)
    db.session.commit()
    flash("Availability record deleted. Re-validate or re-optimise affected rosters.", "success")
    return redirect(url_for("availability.index"))
