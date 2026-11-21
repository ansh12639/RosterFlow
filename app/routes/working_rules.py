from datetime import date, time

from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Brand, CoverageOverride, Process, WorkingRule
from app.models.working_rule import WEEKDAY_SHORT

working_rules_bp = Blueprint("working_rules", __name__, url_prefix="/working-rules")

PRESETS = {
    "365": ([1] * 7, True, "365-day operations (incl. Sundays & public holidays)"),
    "DAILY": ([1] * 7, False, "Every day, public holidays off"),
    "MONSAT": ([1] * 6 + [0], False, "Mon–Sat (Sundays & public holidays off)"),
    "MONFRI": ([1] * 5 + [0, 0], False, "Mon–Fri"),
}


def _parse_rule_form(form):
    """Returns (minimums, holidays, shift_start, shift_end) or raises ValueError."""
    preset = form.get("preset", "")
    if preset in PRESETS:
        base, holidays, _ = PRESETS[preset]
        staff = max(1, form.get("preset_staff", 1, type=int) or 1)
        minimums = [v * staff for v in base]
    else:
        minimums = []
        for i in range(7):
            value = form.get(f"min_{i}", 0, type=int)
            if value is None or value < 0 or value > 20:
                raise ValueError("Daily minimum staff must be between 0 and 20.")
            minimums.append(value)
        holidays = form.get("operates_public_holidays") == "on"
    if not any(minimums):
        raise ValueError("The process must operate on at least one weekday.")
    try:
        start = time.fromisoformat(form.get("shift_start") or "10:00")
        end = time.fromisoformat(form.get("shift_end") or "19:00")
    except ValueError:
        raise ValueError("Enter valid shift times.")
    if end <= start:
        raise ValueError("Shift end must be after shift start (overnight shifts are not supported).")
    return minimums, holidays, start, end


@working_rules_bp.get("/")
def index():
    rules = (WorkingRule.query.join(Brand).join(Process)
             .order_by(WorkingRule.active.desc(), Brand.name, Process.code).all())
    overrides = CoverageOverride.query.order_by(CoverageOverride.override_date.desc()).all()
    return render_template(
        "working_rules.html", rules=rules, overrides=overrides, presets=PRESETS, weekdays=WEEKDAY_SHORT,
        brands=Brand.query.filter_by(active=True).order_by(Brand.name).all(),
        processes=Process.query.filter_by(active=True).order_by(Process.name).all(),
    )


@working_rules_bp.post("/add")
def add_rule():
    brand = db.session.get(Brand, request.form.get("brand_id", type=int) or 0)
    process = db.session.get(Process, request.form.get("process_id", type=int) or 0)
    if not brand or not brand.active or not process or not process.active:
        flash("Select an active brand and process.", "error")
        return redirect(url_for("working_rules.index"))
    try:
        minimums, holidays, start, end = _parse_rule_form(request.form)
        effective_from = date.fromisoformat(request.form.get("effective_from", "").strip())
        raw_to = request.form.get("effective_to", "").strip()
        effective_to = date.fromisoformat(raw_to) if raw_to else None
    except ValueError as error:
        flash(str(error) if "valid" in str(error) or "must" in str(error) else "Enter valid effective dates.", "error")
        return redirect(url_for("working_rules.index"))
    if effective_to and effective_to < effective_from:
        flash("End date cannot be earlier than start date.", "error")
        return redirect(url_for("working_rules.index"))

    filters = [WorkingRule.brand_id == brand.id, WorkingRule.process_id == process.id,
               WorkingRule.active.is_(True),
               or_(WorkingRule.effective_to.is_(None), WorkingRule.effective_to >= effective_from)]
    if effective_to is not None:
        filters.append(WorkingRule.effective_from <= effective_to)
    if WorkingRule.query.filter(*filters).first():
        flash("An active rule already exists for this brand/process in that period. Edit it, or end-date it first.",
              "error")
        return redirect(url_for("working_rules.index"))

    rule = WorkingRule(brand_id=brand.id, process_id=process.id,
                       rule_name=request.form.get("rule_name", "").strip() or f"{brand.name} {process.code}",
                       operates_public_holidays=holidays, shift_start=start, shift_end=end,
                       effective_from=effective_from, effective_to=effective_to, active=True)
    rule.minimums = minimums
    db.session.add(rule)
    db.session.commit()
    flash(f"Rule created: {rule.schedule_label}. Existing rosters can be re-validated to see the impact.", "success")
    return redirect(url_for("working_rules.index"))


@working_rules_bp.post("/<int:rule_id>/edit")
def edit_rule(rule_id):
    rule = db.get_or_404(WorkingRule, rule_id)
    try:
        minimums, holidays, start, end = _parse_rule_form(request.form)
    except ValueError as error:
        flash(str(error), "error")
        return redirect(url_for("working_rules.index"))
    rule.minimums = minimums
    rule.operates_public_holidays = holidays
    rule.shift_start, rule.shift_end = start, end
    rule.rule_name = request.form.get("rule_name", "").strip() or rule.rule_name
    raw_to = request.form.get("effective_to", "").strip()
    if raw_to:
        try:
            rule.effective_to = date.fromisoformat(raw_to)
        except ValueError:
            flash("Enter a valid end date.", "error")
            return redirect(url_for("working_rules.index"))
    db.session.commit()
    flash(f"Rule updated ({rule.schedule_label}). Use 'Re-validate' on a roster to see the effect.", "success")
    return redirect(url_for("working_rules.index"))


@working_rules_bp.post("/<int:rule_id>/toggle")
def toggle_rule(rule_id):
    rule = db.get_or_404(WorkingRule, rule_id)
    rule.active = not rule.active
    db.session.commit()
    flash("Working rule activated." if rule.active else "Working rule deactivated.", "success")
    return redirect(url_for("working_rules.index"))


@working_rules_bp.post("/overrides/add")
def add_override():
    brand = db.session.get(Brand, request.form.get("brand_id", type=int) or 0)
    process = db.session.get(Process, request.form.get("process_id", type=int) or 0)
    staff = request.form.get("minimum_staff", type=int)
    try:
        day = date.fromisoformat(request.form.get("override_date", ""))
    except ValueError:
        day = None
    if not brand or not process or day is None or staff is None or not 0 <= staff <= 20:
        flash("Select brand, process, a date and a minimum staff between 0 and 20.", "error")
        return redirect(url_for("working_rules.index") + "#overrides")
    db.session.add(CoverageOverride(brand_id=brand.id, process_id=process.id, override_date=day,
                                    minimum_staff=staff, reason=request.form.get("reason", "").strip()[:150] or None))
    try:
        db.session.commit()
        flash("Date-specific requirement added.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("An override already exists for that brand/process and date.", "error")
    return redirect(url_for("working_rules.index") + "#overrides")


@working_rules_bp.post("/overrides/<int:override_id>/delete")
def delete_override(override_id):
    db.session.delete(db.get_or_404(CoverageOverride, override_id))
    db.session.commit()
    flash("Override deleted.", "success")
    return redirect(url_for("working_rules.index") + "#overrides")
