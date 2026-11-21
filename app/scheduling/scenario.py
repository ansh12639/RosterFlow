"""Scheduling inputs for one month plus fast lookup helpers."""
from __future__ import annotations

import math
from calendar import monthrange
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

WORKING = "WORKING"
WEEKLY_OFF = "WEEKLY_OFF"
PUBLIC_HOLIDAY = "PUBLIC_HOLIDAY"
LEAVE = "LEAVE"
COMP_OFF = "COMP_OFF"
UNAVAILABLE = "UNAVAILABLE"
UNASSIGNED = "UNASSIGNED"

# Days that count as rest when checking the weekly-off rule. Leave and comp-off
# do NOT count: an employee on leave still earns their weekly off.
REST_STATUSES = {WEEKLY_OFF, PUBLIC_HOLIDAY}
ABSENCE_STATUS = {"PLANNED_LEAVE": LEAVE, "COMP_OFF": COMP_OFF, "UNAVAILABLE": UNAVAILABLE, "WEEKLY_OFF": WEEKLY_OFF}
STATUS_LABEL = {
    WORKING: "Working",
    WEEKLY_OFF: "Weekly off",
    PUBLIC_HOLIDAY: "Public holiday",
    LEAVE: "Approved leave",
    COMP_OFF: "Comp-off",
    UNAVAILABLE: "Unavailable",
    UNASSIGNED: "No assignment",
}
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DEFAULT_SHIFT = (time(10, 0), time(19, 0))


@dataclass(frozen=True)
class EmployeeIn:
    id: int
    name: str
    pod_id: int | None = None
    weekly_offs: int = 1
    active: bool = True


@dataclass(frozen=True)
class RuleIn:
    brand_id: int
    process_id: int
    minimums: tuple  # 7 ints, Mon..Sun; 0 = closed
    on_holidays: bool = False
    shift_start: time = DEFAULT_SHIFT[0]
    shift_end: time = DEFAULT_SHIFT[1]
    effective_from: date = date.min
    effective_to: date | None = None


@dataclass(frozen=True)
class AssignmentIn:
    employee_id: int
    brand_id: int
    process_id: int
    priority: int = 1  # 1 primary, 2+ backup
    effective_from: date = date.min
    effective_to: date | None = None


@dataclass(frozen=True)
class AbsenceIn:
    employee_id: int
    start: date
    end: date
    kind: str  # PLANNED_LEAVE / COMP_OFF / UNAVAILABLE
    note: str = ""


@dataclass(frozen=True)
class WeeklyOffIn:
    employee_id: int
    weekday: int
    kind: str = "PREFERRED"  # or FIXED
    effective_from: date = date.min
    effective_to: date | None = None


def _active(item, day):
    return item.effective_from <= day and (item.effective_to is None or item.effective_to >= day)


@dataclass
class Scenario:
    year: int
    month: int
    employees: list
    rules: list
    assignments: list
    absences: list = field(default_factory=list)
    weekly_offs: list = field(default_factory=list)
    holidays: dict = field(default_factory=dict)  # date -> name
    overrides: dict = field(default_factory=dict)  # (brand, process, date) -> (min, reason)
    brand_names: dict = field(default_factory=dict)
    process_names: dict = field(default_factory=dict)
    max_span_hours: float = 9.0
    max_covers_per_day: int = 1

    def __post_init__(self):
        self.start = date(self.year, self.month, 1)
        self.end = date(self.year, self.month, monthrange(self.year, self.month)[1])
        self.days = [self.start + timedelta(days=i) for i in range((self.end - self.start).days + 1)]
        self.all_employees = {e.id: e for e in self.employees}
        self.active_employees = {e.id: e for e in self.employees if e.active}

        self._rules = defaultdict(list)
        for r in self.rules:
            self._rules[(r.brand_id, r.process_id)].append(r)
        self.pairs = sorted(set(self._rules) | {(b, p) for (b, p, _d) in self.overrides})

        self._primary = defaultdict(list)
        self._backup = defaultdict(list)
        self._emp_assignments = defaultdict(list)
        for a in self.assignments:
            target = self._primary if a.priority <= 1 else self._backup
            target[(a.brand_id, a.process_id)].append(a)
            self._emp_assignments[a.employee_id].append(a)

        self._absences = defaultdict(list)
        for ab in self.absences:
            self._absences[ab.employee_id].append(ab)
        self._weekly = defaultdict(list)
        for w in self.weekly_offs:
            self._weekly[w.employee_id].append(w)
        self._duty_cache = {}
        self.pod_of = {e.id: e.pod_id for e in self.employees}

    # ------------------------------------------------------------- naming
    def emp_name(self, emp_id):
        e = self.all_employees.get(emp_id)
        return e.name if e else f"Employee #{emp_id}"

    def scope_name(self, brand_id, process_id):
        return f"{self.brand_names.get(brand_id, brand_id)} / {self.process_names.get(process_id, process_id)}"

    # ------------------------------------------------------------- demand
    def rule_for(self, brand_id, process_id, day):
        for r in self._rules.get((brand_id, process_id), []):
            if _active(r, day):
                return r
        return None

    def demand(self, brand_id, process_id, day):
        """Minimum staff required for brand/process on ``day`` (0 = closed)."""
        override = self.overrides.get((brand_id, process_id, day))
        if override is not None:
            return override[0]
        rule = self.rule_for(brand_id, process_id, day)
        if rule is None:
            return 0
        if day in self.holidays and not rule.on_holidays:
            return 0
        return rule.minimums[day.weekday()]

    def closed_reason(self, brand_id, process_id, day):
        rule = self.rule_for(brand_id, process_id, day)
        if rule is None:
            return "no working rule"
        if day in self.holidays and not rule.on_holidays:
            return f"public holiday ({self.holidays[day]})"
        return f"closed on {WEEKDAYS[day.weekday()]}s"

    def shift(self, brand_id, process_id, day):
        rule = self.rule_for(brand_id, process_id, day)
        return (rule.shift_start, rule.shift_end) if rule else DEFAULT_SHIFT

    # ------------------------------------------------------------- assignments
    def primaries(self, brand_id, process_id, day):
        return [a.employee_id for a in self._primary.get((brand_id, process_id), []) if _active(a, day)]

    def backups(self, brand_id, process_id, day):
        rows = [a for a in self._backup.get((brand_id, process_id), []) if _active(a, day)]
        return [a.employee_id for a in sorted(rows, key=lambda a: (a.priority, a.employee_id))]

    def has_primary(self, emp_id):
        return any(a.priority <= 1 for a in self._emp_assignments.get(emp_id, []))

    def knows_process(self, emp_id, process_id, day):
        return any(a.process_id == process_id and _active(a, day) for a in self._emp_assignments.get(emp_id, []))

    def duties(self, emp_id, day):
        """Brand/process pairs this employee must cover when working on ``day``."""
        key = (emp_id, day)
        if key not in self._duty_cache:
            self._duty_cache[key] = sorted(
                {
                    (a.brand_id, a.process_id)
                    for a in self._emp_assignments.get(emp_id, [])
                    if a.priority <= 1 and _active(a, day) and self.demand(a.brand_id, a.process_id, day) > 0
                }
            )
        return self._duty_cache[key]

    # ------------------------------------------------------------- availability
    def absence(self, emp_id, day):
        for ab in self._absences.get(emp_id, []):
            if ab.start <= day <= ab.end:
                return ab
        return None

    def fixed_off(self, emp_id, day):
        return any(
            w.kind == "FIXED" and w.weekday == day.weekday() and _active(w, day)
            for w in self._weekly.get(emp_id, [])
        )

    def preferred_weekdays(self, emp_id, day):
        return {w.weekday for w in self._weekly.get(emp_id, []) if w.kind == "PREFERRED" and _active(w, day)}

    # ------------------------------------------------------------- weeks
    def weeks(self):
        """Mon–Sun weeks owned by this month.

        A week belongs to the month that contains its Sunday, so a week that
        straddles two months is checked exactly once (by the later month).
        Returns lists of in-month dates.
        """
        groups = defaultdict(list)
        for d in self.days:
            sunday = d + timedelta(days=6 - d.weekday())
            groups[sunday].append(d)
        return [days for sunday, days in sorted(groups.items()) if sunday <= self.end]

    def required_offs(self, emp_id, week=None):
        """Weekly offs owed in ``week``; partial weeks are pro-rated (rounded up)."""
        e = self.all_employees.get(emp_id)
        n = e.weekly_offs if e else 1
        if week is None or len(week) >= 7:
            return n
        return min(len(week), math.ceil(n * len(week) / 7))

    # ------------------------------------------------------------- shifts
    def span_hours(self, windows):
        if not windows:
            return 0.0
        start = min(w[0] for w in windows)
        end = max(w[1] for w in windows)
        base = date(2000, 1, 1)
        return (datetime.combine(base, end) - datetime.combine(base, start)).total_seconds() / 3600
