"""Roster validation.

The validator is independent of the generator: it re-checks *any* plan (freshly
generated, manually edited, or an old version after rules/leave changed) against
the current configuration, and explains every problem it finds.

Severity model
  ERROR    – mandatory constraint broken (coverage, approved leave, fixed off,
             incompatible shift, double booking). Blocks publishing unless the
             manager explicitly acknowledges it.
  WARNING  – soft constraint or risk (preference not granted, weekly rest short,
             one person's absence hitting several brands).
  INFO     – worth knowing (worked a public holiday -> comp-off eligible).
"""
from __future__ import annotations

from collections import defaultdict

from .plan import coverage
from .scenario import (REST_STATUSES, STATUS_LABEL, WEEKDAYS, WORKING)


def _fmt(day):
    return day.strftime("%a %d %b")


def employee_shift_windows(sc, plan, emp_id, day, covers_by_emp=None, extra=None):
    covers_by_emp = covers_by_emp if covers_by_emp is not None else plan.covers_by_employee()
    windows = []
    if plan.is_working(emp_id, day):
        windows += [sc.shift(b, p, day) for b, p in sc.duties(emp_id, day)]
    windows += [sc.shift(b, p, day) for b, p in covers_by_emp.get((emp_id, day), [])]
    if extra:
        windows.append(sc.shift(extra[0], extra[1], day))
    return windows


def cover_candidates(sc, plan, brand_id, process_id, day, limit=5, covers_by_emp=None, covers_by_scope=None):
    """Rank employees who could cover brand/process on ``day``.

    Only people already WORKING that day are proposed (we never cancel someone's
    rest automatically). Ranking: designated backup > same pod & knows the
    process > knows the process > same pod; then lowest extra load.
    """
    covers_by_emp = covers_by_emp if covers_by_emp is not None else plan.covers_by_employee()
    covers_by_scope = covers_by_scope if covers_by_scope is not None else plan.covers_by_scope()
    primaries = set(sc.primaries(brand_id, process_id, day))
    backups = sc.backups(brand_id, process_id, day)
    pods = {sc.pod_of.get(e) for e in primaries} - {None}
    already = set(covers_by_scope.get((brand_id, process_id, day), []))
    process_name = sc.process_names.get(process_id, "this process")
    ranked = []
    for emp_id in sc.active_employees:
        if emp_id in primaries or emp_id in already or not plan.is_working(emp_id, day):
            continue
        load = len(covers_by_emp.get((emp_id, day), []))
        if load >= sc.max_covers_per_day:
            continue
        span = sc.span_hours(employee_shift_windows(sc, plan, emp_id, day, covers_by_emp, (brand_id, process_id)))
        if span > sc.max_span_hours:
            continue
        same_pod = sc.pod_of.get(emp_id) in pods
        knows = sc.knows_process(emp_id, process_id, day)
        if emp_id in backups:
            tier, reason = 0, "designated backup"
        elif same_pod and knows:
            tier, reason = 1, f"same pod, handles {process_name} elsewhere"
        elif knows:
            tier, reason = 2, f"handles {process_name} for another brand"
        elif same_pod:
            tier, reason = 3, "same pod"
        else:
            continue
        ranked.append((tier, load, len(sc.duties(emp_id, day)), sc.emp_name(emp_id), emp_id, reason))
    ranked.sort()
    return [dict(employee_id=r[4], name=r[3], reason=r[5]) for r in ranked[:limit]]


def _absence_reason(sc, plan, emp_id, day):
    if emp_id not in sc.active_employees:
        return "inactive employee"
    state = plan.status.get((emp_id, day))
    if state is None:
        return "not rostered"
    label = STATUS_LABEL.get(state.status, state.status).lower()
    return f"{label}{' – ' + state.note if state.note and state.status != WORKING else ''}"


def validate(sc, plan):
    conflicts = []
    covers_by_scope = plan.covers_by_scope()
    covers_by_emp = plan.covers_by_employee()

    def add(**kw):
        kw.setdefault("brand_id", None)
        kw.setdefault("process_id", None)
        kw.setdefault("employee_id", None)
        kw.setdefault("required_staff", None)
        kw.setdefault("available_staff", None)
        kw.setdefault("suggestion", None)
        kw.setdefault("candidates", [])
        conflicts.append(kw)

    # 1. Coverage per brand / process / day --------------------------------
    gaps_caused = defaultdict(list)  # (emp, day) -> [scope names]
    for day in sc.days:
        for b, p in sc.pairs:
            need = sc.demand(b, p, day)
            if need <= 0:
                continue
            working, cover_emps = coverage(sc, plan, b, p, day, covers_by_scope)
            have = len(working) + len(cover_emps)
            if have >= need:
                continue
            assigned = sc.primaries(b, p, day)
            scope = sc.scope_name(b, p)
            candidates = cover_candidates(sc, plan, b, p, day, covers_by_emp=covers_by_emp, covers_by_scope=covers_by_scope)
            if candidates:
                suggestion = "Assign a cover: " + "; ".join(f"{c['name']} ({c['reason']})" for c in candidates[:3])
            else:
                suggestion = ("No working employee with a compatible shift knows this process. "
                              "Reschedule an assigned employee's weekly off, cancel/shift leave, or add a backup assignment.")
            if not assigned:
                add(conflict_type="UNASSIGNED_REQUIREMENT", severity="ERROR", roster_date=day, brand_id=b,
                    process_id=p, required_staff=need, available_staff=have,
                    message=f"{scope} operates on {_fmt(day)} (needs {need}) but no employee is assigned to it.",
                    suggestion="Create an assignment for this brand/process. " + suggestion, candidates=candidates)
                continue
            missing = [e for e in assigned if e not in working]
            reasons = ", ".join(f"{sc.emp_name(e)} ({_absence_reason(sc, plan, e, day)})" for e in missing)
            if len(assigned) == 1:
                lead = f"Single-resource scope: its only assignee {sc.emp_name(assigned[0])} is unavailable."
            else:
                lead = (f"{len(working)} of {len(assigned)} assigned employees working"
                        f"{' + ' + str(len(cover_emps)) + ' cover' if cover_emps else ''}; remaining staff cannot meet the minimum.")
            add(conflict_type="COVERAGE_GAP", severity="ERROR", roster_date=day, brand_id=b, process_id=p,
                required_staff=need, available_staff=have,
                message=f"{scope} on {_fmt(day)} has {have}/{need} staff. {lead} Not working: {reasons or 'n/a'}.",
                suggestion=suggestion, candidates=candidates)
            for e in missing:
                gaps_caused[(e, day)].append(sc.brand_names.get(b, str(b)))

    # 2. One absence creating gaps across several brands --------------------
    for (emp_id, day), brands in sorted(gaps_caused.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        unique = sorted(set(brands))
        if len(unique) > 1:
            add(conflict_type="MULTI_BRAND_IMPACT", severity="WARNING", roster_date=day, employee_id=emp_id,
                message=f"{sc.emp_name(emp_id)} being off on {_fmt(day)} leaves {len(unique)} brands short: {', '.join(unique)}.",
                suggestion="Consider moving this employee's off day, or assign covers for each brand.")

    # 3. Per-employee daily checks ------------------------------------------
    for emp_id in sc.active_employees:
        name = sc.emp_name(emp_id)
        for day in sc.days:
            state = plan.status.get((emp_id, day))
            if state is None:
                continue
            working = state.status == WORKING
            cover_list = covers_by_emp.get((emp_id, day), [])
            absence = sc.absence(emp_id, day)
            if working and absence:
                add(conflict_type="LEAVE_CONFLICT", severity="ERROR", roster_date=day, employee_id=emp_id,
                    message=f"{name} is rostered to work on {_fmt(day)} but has approved {absence.kind.replace('_', ' ').lower()}.",
                    suggestion="Set the day back to leave, or withdraw the leave approval first.")
            if working and sc.fixed_off(emp_id, day):
                add(conflict_type="RULE_VIOLATION", severity="ERROR", roster_date=day, employee_id=emp_id,
                    message=f"{name} is rostered on {_fmt(day)}, which is a FIXED weekly off ({WEEKDAYS[day.weekday()]}).",
                    suggestion="Fixed weekly offs are contractual; set the day to weekly off or change the employee's weekly-off rule.")
            if cover_list and not working:
                add(conflict_type="DOUBLE_BOOKING", severity="ERROR", roster_date=day, employee_id=emp_id,
                    message=f"{name} is assigned to cover {len(cover_list)} duty(ies) on {_fmt(day)} while marked "
                            f"{STATUS_LABEL.get(state.status, state.status).lower()}.",
                    suggestion="Remove the cover or mark the employee as working.")
            if len(cover_list) > sc.max_covers_per_day:
                add(conflict_type="DOUBLE_BOOKING", severity="WARNING", roster_date=day, employee_id=emp_id,
                    message=f"{name} is covering {len(cover_list)} extra duties on {_fmt(day)} on top of their own brands "
                            f"(limit {sc.max_covers_per_day}).",
                    suggestion="Spread the covers across other candidates.")
            windows = employee_shift_windows(sc, plan, emp_id, day, covers_by_emp)
            span = sc.span_hours(windows)
            if span > sc.max_span_hours:
                add(conflict_type="INCOMPATIBLE_SHIFT", severity="ERROR", roster_date=day, employee_id=emp_id,
                    message=f"{name}'s responsibilities on {_fmt(day)} span {span:.1f}h "
                            f"({min(w[0] for w in windows):%H:%M}–{max(w[1] for w in windows):%H:%M}), "
                            f"over the {sc.max_span_hours:g}h shift limit.",
                    suggestion="Move one of the overlapping duties to another employee.")
            if working and day in sc.holidays and sc.duties(emp_id, day):
                add(conflict_type="COMP_OFF_ELIGIBLE", severity="INFO", roster_date=day, employee_id=emp_id,
                    message=f"{name} works on {sc.holidays[day]} ({_fmt(day)}) and is eligible for a comp-off.",
                    suggestion="Record a comp-off for a later date on the Availability page.")

        # 4. Weekly rules ------------------------------------------------------
        if not sc.has_primary(emp_id):
            continue
        for week in sc.weeks():
            states = [plan.status.get((emp_id, d)) for d in week]
            rest = sum(1 for s in states if s and s.status in REST_STATUSES)
            on_leave_all_week = all(s and s.status not in (WORKING,) and s.status not in REST_STATUSES for s in states)
            required = sc.required_offs(emp_id, week)
            if rest < required and not on_leave_all_week:
                worked = sum(1 for s in states if s and s.status == WORKING)
                add(conflict_type="REST_VIOLATION", severity="WARNING", roster_date=week[0], employee_id=emp_id,
                    message=f"{name} gets {rest} of {required} required weekly off(s) in the week of {_fmt(week[0])} "
                            f"(working {worked} day(s)).",
                    suggestion="Give the employee an off day this week; arrange a cover if it creates a gap.")
            preferred_days = [d for d in week if d.weekday() in sc.preferred_weekdays(emp_id, d)]
            if preferred_days and not any(plan.status[(emp_id, d)].status != WORKING for d in preferred_days):
                actual = [d for d, s in zip(week, states) if s and s.status == WEEKLY_OFF_STATUS]
                where = f"off given on {', '.join(_fmt(d) for d in actual)}" if actual else "no weekly off given"
                add(conflict_type="PREFERENCE_VIOLATION", severity="WARNING", roster_date=preferred_days[0],
                    employee_id=emp_id,
                    message=f"{name}'s preferred off ({', '.join(_fmt(d) for d in preferred_days)}) was not granted – "
                            f"required client coverage takes priority; {where}.",
                    suggestion="Acceptable by policy. Swap with a colleague if the employee requests it.")
    return conflicts


WEEKLY_OFF_STATUS = "WEEKLY_OFF"


def summarize(conflicts):
    counts = defaultdict(int)
    for c in conflicts:
        counts[c["severity"]] += 1
    return dict(errors=counts["ERROR"], warnings=counts["WARNING"], info=counts["INFO"])
