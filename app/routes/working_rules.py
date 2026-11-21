from datetime import date

from flask import Blueprint, render_template, request, redirect, url_for, flash
from sqlalchemy import or_

from app.extensions import db
from app.models import WorkingRule, Brand, Process

working_rules_bp = Blueprint("working_rules", __name__, url_prefix="/working-rules")


@working_rules_bp.get("/")
def index():
    rules = WorkingRule.query.order_by(WorkingRule.effective_from.desc()).all()

    brands = Brand.query.filter_by(active=True).order_by(Brand.name).all()

    processes = Process.query.filter_by(active=True).order_by(Process.name).all()

    return render_template(
        "working_rules.html",
        rules=rules,
        brands=brands,
        processes=processes,
    )


@working_rules_bp.post("/add")
def add_rule():
    brand_id = request.form.get("brand_id", type=int)
    process_id = request.form.get("process_id", type=int)

    rule_name = request.form.get("rule_name", "").strip()

    effective_from_raw = request.form.get("effective_from", "").strip()
    effective_to_raw = request.form.get("effective_to", "").strip()

    minimum_staff = request.form.get("minimum_staff", type=int)

    brand = db.session.get(Brand, brand_id) if brand_id else None
    process = db.session.get(Process, process_id) if process_id else None

    if not brand or not brand.active:
        flash("Select a valid active brand.", "error")
        return redirect(url_for("working_rules.index"))

    if not process or not process.active:
        flash("Select a valid active process.", "error")
        return redirect(url_for("working_rules.index"))

    if not rule_name:
        flash("Rule name is required.", "error")
        return redirect(url_for("working_rules.index"))

    try:
        effective_from = date.fromisoformat(effective_from_raw)
        effective_to = (
            date.fromisoformat(effective_to_raw) if effective_to_raw else None
        )
    except ValueError:
        flash("Enter valid effective dates.", "error")
        return redirect(url_for("working_rules.index"))

    if effective_to and effective_to < effective_from:
        flash("End date cannot be earlier than start date.", "error")
        return redirect(url_for("working_rules.index"))

    if minimum_staff is None or minimum_staff < 1:
        flash("Minimum staff must be at least 1.", "error")
        return redirect(url_for("working_rules.index"))

    operates_sunday = request.form.get("operates_sunday") == "on"
    operates_public_holidays = request.form.get("operates_public_holidays") == "on"
    operates_monday_to_saturday = (
        request.form.get("operates_monday_to_saturday") == "on"
    )

    if not any(
        [
            operates_sunday,
            operates_public_holidays,
            operates_monday_to_saturday,
        ]
    ):
        flash("Select at least one operating schedule.", "error")
        return redirect(url_for("working_rules.index"))

    # Prevent overlapping active rules for the same brand and process.
    overlap_filters = [
        WorkingRule.brand_id == brand.id,
        WorkingRule.process_id == process.id,
        WorkingRule.active.is_(True),
        or_(
            WorkingRule.effective_to.is_(None),
            WorkingRule.effective_to >= effective_from,
        ),
    ]

    if effective_to is not None:
        overlap_filters.append(WorkingRule.effective_from <= effective_to)

    existing_rule = WorkingRule.query.filter(*overlap_filters).first()

    if existing_rule:
        flash(
            "An active working rule already exists for this brand "
            "and process during the selected dates.",
            "error",
        )
        return redirect(url_for("working_rules.index"))

    rule = WorkingRule(
        brand_id=brand.id,
        process_id=process.id,
        rule_name=rule_name,
        operates_sunday=operates_sunday,
        operates_public_holidays=operates_public_holidays,
        operates_monday_to_saturday=operates_monday_to_saturday,
        minimum_staff=minimum_staff,
        effective_from=effective_from,
        effective_to=effective_to,
        active=True,
    )

    db.session.add(rule)
    db.session.commit()

    flash("Working rule created successfully.", "success")
    return redirect(url_for("working_rules.index"))


@working_rules_bp.post("/<int:rule_id>/toggle")
def toggle_rule(rule_id):
    rule = db.get_or_404(WorkingRule, rule_id)

    rule.active = not rule.active
    db.session.commit()

    flash(
        "Working rule activated." if rule.active else "Working rule deactivated.",
        "success",
    )

    return redirect(url_for("working_rules.index"))
