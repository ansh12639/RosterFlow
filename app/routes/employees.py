from flask import Blueprint, render_template, request, redirect, url_for, flash
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Employee, Pod

employees_bp = Blueprint("employees", __name__, url_prefix="/employees")


@employees_bp.get("/")
def index():
    search = request.args.get("search", "").strip()
    status = request.args.get("status", "all")

    query = Employee.query

    if search:
        query = query.filter(
            db.or_(
                Employee.full_name.ilike(f"%{search}%"),
                Employee.employee_code.ilike(f"%{search}%"),
                Employee.email.ilike(f"%{search}%"),
            )
        )

    if status == "active":
        query = query.filter_by(active=True)
    elif status == "inactive":
        query = query.filter_by(active=False)

    employees = query.order_by(Employee.employee_code).all()
    return render_template(
        "employees/list.html",
        employees=employees,
        pods=Pod.query.order_by(Pod.name).all(),
        search=search,
        status=status,
    )


@employees_bp.post("/add")
def add():
    employee_code = request.form.get("employee_code", "").strip()
    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    pod_id = request.form.get("pod_id") or None
    designation = request.form.get("designation", "").strip() or None
    weekly_offs = request.form.get("weekly_offs_per_week", 1, type=int)

    if weekly_offs is None or not 0 <= weekly_offs <= 3:
        flash("Weekly offs per week must be between 0 and 3.", "error")
        return redirect(url_for("employees.index"))

    if not employee_code or not full_name or not email:
        flash("Employee code, name and email are required.", "error")
        return redirect(url_for("employees.index"))

    employee = Employee(
        employee_code=employee_code,
        full_name=full_name,
        email=email,
        phone=phone or None,
        pod_id=int(pod_id) if pod_id else None,
        designation=designation,
        weekly_offs_per_week=weekly_offs,
        active=True,
    )

    try:
        db.session.add(employee)
        db.session.commit()
        flash("Employee added successfully.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Employee code or email already exists.", "error")

    return redirect(url_for("employees.index"))


@employees_bp.post("/<int:employee_id>/edit")
def edit(employee_id):
    employee = db.get_or_404(Employee, employee_id)

    employee.employee_code = request.form.get("employee_code", "").strip()
    employee.full_name = request.form.get("full_name", "").strip()
    employee.email = request.form.get("email", "").strip()
    employee.phone = request.form.get("phone", "").strip() or None

    pod_id = request.form.get("pod_id") or None
    employee.pod_id = int(pod_id) if pod_id else None
    employee.designation = request.form.get("designation", "").strip() or None
    weekly_offs = request.form.get("weekly_offs_per_week", employee.weekly_offs_per_week, type=int)

    if not employee.employee_code or not employee.full_name or not employee.email:
        db.session.rollback()
        flash("Employee code, name and email are required.", "error")
        return redirect(url_for("employees.index"))
    if weekly_offs is None or not 0 <= weekly_offs <= 3:
        db.session.rollback()
        flash("Weekly offs per week must be between 0 and 3.", "error")
        return redirect(url_for("employees.index"))
    employee.weekly_offs_per_week = weekly_offs

    try:
        db.session.commit()
        flash("Employee updated successfully.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Employee code or email is already in use.", "error")

    return redirect(url_for("employees.index"))


@employees_bp.post("/<int:employee_id>/toggle")
def toggle(employee_id):
    employee = db.get_or_404(Employee, employee_id)

    employee.active = not employee.active

    db.session.commit()

    message = "Employee activated." if employee.active else "Employee deactivated."

    flash(message, "success")
    return redirect(url_for("employees.index"))
