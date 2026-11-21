from datetime import date

from flask import Blueprint, render_template, request, redirect, url_for, flash
from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Pod, Employee, Brand, Process, Assignment

pods_bp = Blueprint("pods", __name__, url_prefix="/pods")


@pods_bp.get("/")
def index():
    pods = Pod.query.order_by(Pod.name).all()
    employees = Employee.query.order_by(Employee.full_name).all()
    brands = Brand.query.filter_by(active=True).order_by(Brand.name).all()
    processes = Process.query.filter_by(active=True).order_by(Process.name).all()

    assignments = Assignment.query.order_by(Assignment.created_at.desc()).all()

    return render_template(
        "pods.html",
        pods=pods,
        employees=employees,
        brands=brands,
        processes=processes,
        assignments=assignments,
    )


# -------------------------
# Pod management
# -------------------------


@pods_bp.post("/add")
def add_pod():
    name = request.form.get("name", "").strip()

    if not name:
        flash("Pod name is required.", "error")
        return redirect(url_for("pods.index") + "#pods")

    try:
        db.session.add(Pod(name=name))
        db.session.commit()
        flash("Pod created successfully.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("A pod with this name already exists.", "error")

    return redirect(url_for("pods.index") + "#pods")


@pods_bp.post("/<int:pod_id>/edit")
def edit_pod(pod_id):
    pod = db.get_or_404(Pod, pod_id)
    name = request.form.get("name", "").strip()

    if not name:
        flash("Pod name is required.", "error")
        return redirect(url_for("pods.index") + "#pods")

    pod.name = name

    try:
        db.session.commit()
        flash("Pod updated successfully.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("A pod with this name already exists.", "error")

    return redirect(url_for("pods.index") + "#pods")


@pods_bp.post("/<int:pod_id>/assign-employee")
def assign_employee_to_pod(pod_id):
    pod = db.get_or_404(Pod, pod_id)
    employee_id = request.form.get("employee_id", type=int)
    employee = db.session.get(Employee, employee_id) if employee_id else None

    if not employee:
        flash("Select a valid employee.", "error")
        return redirect(url_for("pods.index") + "#pods")

    if not employee.active:
        flash("Inactive employees cannot be assigned to a pod.", "error")
        return redirect(url_for("pods.index") + "#pods")

    employee.pod_id = pod.id
    db.session.commit()

    flash(f"{employee.full_name} assigned to {pod.name}.", "success")
    return redirect(url_for("pods.index") + "#pods")


@pods_bp.post("/<int:pod_id>/remove-employee")
def remove_employee_from_pod(pod_id):
    pod = db.get_or_404(Pod, pod_id)
    employee_id = request.form.get("employee_id", type=int)
    employee = db.session.get(Employee, employee_id) if employee_id else None

    if not employee or employee.pod_id != pod.id:
        flash("Employee is not assigned to this pod.", "error")
        return redirect(url_for("pods.index") + "#pods")

    if pod.lead_employee_id == employee.id:
        pod.lead_employee_id = None

    employee.pod_id = None
    db.session.commit()

    flash("Employee removed from the pod.", "success")
    return redirect(url_for("pods.index") + "#pods")


@pods_bp.post("/<int:pod_id>/set-lead")
def set_pod_lead(pod_id):
    pod = db.get_or_404(Pod, pod_id)
    employee_id = request.form.get("employee_id", type=int)
    employee = db.session.get(Employee, employee_id) if employee_id else None

    if not employee or employee.pod_id != pod.id:
        flash("The pod lead must be an employee assigned to this pod.", "error")
        return redirect(url_for("pods.index") + "#pods")

    if not employee.active:
        flash("An inactive employee cannot be a pod lead.", "error")
        return redirect(url_for("pods.index") + "#pods")

    pod.lead_employee_id = employee.id
    db.session.commit()

    flash(f"{employee.full_name} is now the lead of {pod.name}.", "success")
    return redirect(url_for("pods.index") + "#pods")


# -------------------------
# Employee brand/process assignments
# -------------------------


@pods_bp.post("/assignments/add")
def add_assignment():
    employee_id = request.form.get("employee_id", type=int)
    brand_id = request.form.get("brand_id", type=int)
    process_id = request.form.get("process_id", type=int)
    effective_from_raw = request.form.get("effective_from", "").strip()
    effective_to_raw = request.form.get("effective_to", "").strip()
    priority = request.form.get("priority", 1, type=int)

    employee = db.session.get(Employee, employee_id) if employee_id else None
    brand = db.session.get(Brand, brand_id) if brand_id else None
    process = db.session.get(Process, process_id) if process_id else None

    if not employee or not employee.active:
        flash("Select a valid active employee.", "error")
        return redirect(url_for("pods.index") + "#assignments")

    if not brand or not brand.active:
        flash("Select a valid active brand.", "error")
        return redirect(url_for("pods.index") + "#assignments")

    if not process or not process.active:
        flash("Select a valid active process.", "error")
        return redirect(url_for("pods.index") + "#assignments")

    try:
        effective_from = date.fromisoformat(effective_from_raw)
        effective_to = (
            date.fromisoformat(effective_to_raw) if effective_to_raw else None
        )
    except ValueError:
        flash("Enter valid assignment dates.", "error")
        return redirect(url_for("pods.index") + "#assignments")

    if effective_to and effective_to < effective_from:
        flash("End date cannot be earlier than start date.", "error")
        return redirect(url_for("pods.index") + "#assignments")

    if priority < 1:
        flash("Priority must be at least 1.", "error")
        return redirect(url_for("pods.index") + "#assignments")

    # Prevent overlapping active assignments for the same employee,
    # brand and process.
    overlap_filters = [
        Assignment.employee_id == employee.id,
        Assignment.brand_id == brand.id,
        Assignment.process_id == process.id,
        Assignment.active.is_(True),
        or_(
            Assignment.effective_to.is_(None),
            Assignment.effective_to >= effective_from,
        ),
    ]

    # Only apply this condition when the new assignment has an end date.
    if effective_to is not None:
        overlap_filters.append(Assignment.effective_from <= effective_to)

    overlapping_assignment = Assignment.query.filter(*overlap_filters).first()

    if overlapping_assignment:
        flash(
            "This employee already has an overlapping active assignment "
            "for this brand and process.",
            "error",
        )
        return redirect(url_for("pods.index") + "#assignments")

    assignment = Assignment(
        employee_id=employee.id,
        brand_id=brand.id,
        process_id=process.id,
        effective_from=effective_from,
        effective_to=effective_to,
        priority=priority,
        active=True,
    )

    db.session.add(assignment)
    db.session.commit()

    flash("Employee assignment created successfully.", "success")
    return redirect(url_for("pods.index") + "#assignments")


@pods_bp.post("/assignments/<int:assignment_id>/close")
def close_assignment(assignment_id):
    assignment = db.get_or_404(Assignment, assignment_id)

    assignment.active = False
    db.session.commit()

    flash("Assignment deactivated. Its history has been preserved.", "success")
    return redirect(url_for("pods.index") + "#assignments")
