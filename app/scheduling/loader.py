"""Build a Scenario for a month from the database."""
from calendar import monthrange
from datetime import date

from flask import current_app
from sqlalchemy import or_

from app.models import (Assignment, Availability, Brand, CoverageOverride, Employee,
                        EmployeeWeeklyOff, Holiday, Process, WorkingRule)
from .scenario import (AbsenceIn, AssignmentIn, EmployeeIn, RuleIn, Scenario, WeeklyOffIn)


def _overlaps(model, start, end):
    return [model.effective_from <= end, or_(model.effective_to.is_(None), model.effective_to >= start)]


def load_scenario(year, month):
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])

    brands = {b.id: b for b in Brand.query.all()}
    processes = {p.id: p for p in Process.query.all()}
    active_brand = {i for i, b in brands.items() if b.active}
    active_process = {i for i, p in processes.items() if p.active}

    def in_scope(brand_id, process_id):
        # Inactive brands/processes generate no demand and no duties.
        return brand_id in active_brand and process_id in active_process

    employees = [
        EmployeeIn(e.id, e.full_name, e.pod_id, max(0, e.weekly_offs_per_week or 0), e.active)
        for e in Employee.query.order_by(Employee.id).all()
    ]
    rules = [
        RuleIn(r.brand_id, r.process_id, r.minimums, r.operates_public_holidays,
               r.shift_start, r.shift_end, r.effective_from, r.effective_to)
        for r in WorkingRule.query.filter(WorkingRule.active.is_(True), *_overlaps(WorkingRule, start, end))
        .order_by(WorkingRule.effective_from.desc()).all()
        if in_scope(r.brand_id, r.process_id)
    ]
    assignments = [
        AssignmentIn(a.employee_id, a.brand_id, a.process_id, a.priority, a.effective_from, a.effective_to)
        for a in Assignment.query.filter(Assignment.active.is_(True), *_overlaps(Assignment, start, end)).all()
        if in_scope(a.brand_id, a.process_id)
    ]
    absences = [
        AbsenceIn(a.employee_id, a.start_date, a.end_date, a.availability_type, a.notes or "")
        for a in Availability.query.filter(
            Availability.approval_status == "APPROVED",
            Availability.availability_type != "WEEKLY_OFF",
            Availability.start_date <= end, Availability.end_date >= start,
        ).all()
    ]
    weekly_offs = [
        WeeklyOffIn(w.employee_id, w.weekday, w.kind, w.effective_from, w.effective_to)
        for w in EmployeeWeeklyOff.query.filter(*_overlaps(EmployeeWeeklyOff, start, end)).all()
    ]
    holidays = {
        h.holiday_date: h.name
        for h in Holiday.query.filter(Holiday.holiday_date >= start, Holiday.holiday_date <= end).all()
    }
    overrides = {
        (o.brand_id, o.process_id, o.override_date): (o.minimum_staff, o.reason or "")
        for o in CoverageOverride.query.filter(
            CoverageOverride.override_date >= start, CoverageOverride.override_date <= end).all()
        if in_scope(o.brand_id, o.process_id)
    }
    config = current_app.config
    return Scenario(
        year=year, month=month, employees=employees, rules=rules, assignments=assignments,
        absences=absences, weekly_offs=weekly_offs, holidays=holidays, overrides=overrides,
        brand_names={i: b.name for i, b in brands.items()},
        process_names={i: p.name for i, p in processes.items()},
        max_span_hours=float(config.get("MAX_SHIFT_SPAN_HOURS", 9)),
        max_covers_per_day=int(config.get("MAX_COVERS_PER_DAY", 1)),
    )
