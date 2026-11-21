from flask import Blueprint, render_template, request, redirect, url_for, flash
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Brand, Process

catalog_bp = Blueprint("catalog", __name__, url_prefix="/catalog")


@catalog_bp.get("/")
def index():
    brands = Brand.query.order_by(Brand.name).all()
    processes = Process.query.order_by(Process.name).all()

    return render_template("catalog.html", brands=brands, processes=processes)


# -------------------------
# BRAND MANAGEMENT
# -------------------------


@catalog_bp.post("/brands/add")
def add_brand():
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()

    if not name:
        flash("Brand name is required.", "error")
        return redirect(url_for("catalog.index") + "#brands")

    brand = Brand(name=name, description=description or None, active=True)

    try:
        db.session.add(brand)
        db.session.commit()
        flash("Brand added successfully.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("This brand name already exists.", "error")

    return redirect(url_for("catalog.index") + "#brands")


@catalog_bp.post("/brands/<int:brand_id>/edit")
def edit_brand(brand_id):
    brand = db.get_or_404(Brand, brand_id)

    name = request.form.get("name", "").strip()

    if not name:
        flash("Brand name is required.", "error")
        return redirect(url_for("catalog.index") + "#brands")

    brand.name = name
    brand.description = request.form.get("description", "").strip() or None

    try:
        db.session.commit()
        flash("Brand updated successfully.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("This brand name is already in use.", "error")

    return redirect(url_for("catalog.index") + "#brands")


@catalog_bp.post("/brands/<int:brand_id>/toggle")
def toggle_brand(brand_id):
    brand = db.get_or_404(Brand, brand_id)

    brand.active = not brand.active
    db.session.commit()

    flash("Brand activated." if brand.active else "Brand deactivated.", "success")

    return redirect(url_for("catalog.index") + "#brands")


# -------------------------
# PROCESS MANAGEMENT
# -------------------------


@catalog_bp.post("/processes/add")
def add_process():
    code = request.form.get("code", "").strip().upper()
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()

    if not code or not name:
        flash("Process code and name are required.", "error")
        return redirect(url_for("catalog.index") + "#processes")

    process = Process(
        code=code, name=name, description=description or None, active=True
    )

    try:
        db.session.add(process)
        db.session.commit()
        flash("Process added successfully.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Process code or name already exists.", "error")

    return redirect(url_for("catalog.index") + "#processes")


@catalog_bp.post("/processes/<int:process_id>/edit")
def edit_process(process_id):
    process = db.get_or_404(Process, process_id)

    code = request.form.get("code", "").strip().upper()
    name = request.form.get("name", "").strip()

    if not code or not name:
        flash("Process code and name are required.", "error")
        return redirect(url_for("catalog.index") + "#processes")

    process.code = code
    process.name = name
    process.description = request.form.get("description", "").strip() or None

    try:
        db.session.commit()
        flash("Process updated successfully.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Process code or name already exists.", "error")

    return redirect(url_for("catalog.index") + "#processes")


@catalog_bp.post("/processes/<int:process_id>/toggle")
def toggle_process(process_id):
    process = db.get_or_404(Process, process_id)

    process.active = not process.active
    db.session.commit()

    flash("Process activated." if process.active else "Process deactivated.", "success")

    return redirect(url_for("catalog.index") + "#processes")
