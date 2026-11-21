from datetime import date

from flask import Blueprint, render_template, request, redirect, url_for, flash
from sqlalchemy import and_
from sqlalchemy import or_
from app.extensions import db
from app.models import Holiday

holidays_bp = Blueprint("holidays", __name__, url_prefix="/holidays")


@holidays_bp.get("/")
def index():
    holidays = Holiday.query.order_by(Holiday.holiday_date.desc()).all()

    return render_template(
        "holidays.html",
        holidays=holidays,
    )


@holidays_bp.post("/add")
def add_holiday():
    name = request.form.get("name", "").strip()
    date_raw = request.form.get("holiday_date", "").strip()
    region = request.form.get("region", "").strip()

    if not name:
        flash("Holiday name is required.", "error")
        return redirect(url_for("holidays.index"))

    try:
        holiday_date = date.fromisoformat(date_raw)
    except ValueError:
        flash("Enter a valid holiday date.", "error")
        return redirect(url_for("holidays.index"))

    if len(name) > 150 or len(region) > 100:
        flash("Holiday name or region is too long.", "error")
        return redirect(url_for("holidays.index"))

    # Check for duplicate holidays on the same date.
    duplicate_query = Holiday.query.filter(Holiday.holiday_date == holiday_date)

    if region:
        duplicate_query = duplicate_query.filter(
            or_(
                Holiday.region == region,
                Holiday.region.is_(None),
            )
        )
    else:
        duplicate_query = duplicate_query.filter(Holiday.region.is_(None))

    duplicate = duplicate_query.first()

    if duplicate:
        flash(
            "A holiday already exists for this date and region.",
            "error",
        )
        return redirect(url_for("holidays.index"))

    holiday = Holiday(
        name=name,
        holiday_date=holiday_date,
        region=region or None,
    )

    db.session.add(holiday)
    db.session.commit()

    flash("Public holiday added successfully.", "success")
    return redirect(url_for("holidays.index"))


@holidays_bp.post("/<int:holiday_id>/delete")
def delete_holiday(holiday_id):
    holiday = db.get_or_404(Holiday, holiday_id)

    db.session.delete(holiday)
    db.session.commit()

    flash("Holiday deleted successfully.", "success")
    return redirect(url_for("holidays.index"))
