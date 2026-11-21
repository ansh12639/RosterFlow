"""In-memory roster representation shared by the engine, validator and store."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .scenario import WORKING


@dataclass
class DayState:
    status: str
    source: str = "AUTO"  # AUTO or MANUAL
    note: str = ""


@dataclass(frozen=True)
class Cover:
    """An employee temporarily covering a brand/process they are not primary on."""

    employee_id: int
    brand_id: int
    process_id: int
    day: object
    source: str = "AUTO"


@dataclass
class Plan:
    status: dict = field(default_factory=dict)  # (employee_id, date) -> DayState
    covers: list = field(default_factory=list)

    def is_working(self, emp_id, day):
        state = self.status.get((emp_id, day))
        return state is not None and state.status == WORKING

    def covers_by_scope(self):
        index = defaultdict(list)
        for c in self.covers:
            index[(c.brand_id, c.process_id, c.day)].append(c.employee_id)
        return index

    def covers_by_employee(self):
        index = defaultdict(list)
        for c in self.covers:
            index[(c.employee_id, c.day)].append((c.brand_id, c.process_id))
        return index


def coverage(scenario, plan, brand_id, process_id, day, covers_index=None):
    """Return (working_primaries, cover_employees) for a scope on a day."""
    working = [
        e for e in scenario.primaries(brand_id, process_id, day)
        if e in scenario.active_employees and plan.is_working(e, day)
    ]
    covers_index = covers_index if covers_index is not None else plan.covers_by_scope()
    return working, list(covers_index.get((brand_id, process_id, day), []))


def entries_for(scenario, plan):
    """Expand the plan into duty rows: one per (employee, brand, process, day)."""
    rows = []
    for (emp_id, day), state in plan.status.items():
        if state.status != WORKING:
            continue
        for brand_id, process_id in scenario.duties(emp_id, day):
            start, end = scenario.shift(brand_id, process_id, day)
            rows.append(dict(employee_id=emp_id, brand_id=brand_id, process_id=process_id,
                             roster_date=day, shift_start=start, shift_end=end,
                             status=WORKING, source=state.source, is_cover=False))
    for c in plan.covers:
        start, end = scenario.shift(c.brand_id, c.process_id, c.day)
        rows.append(dict(employee_id=c.employee_id, brand_id=c.brand_id, process_id=c.process_id,
                         roster_date=c.day, shift_start=start, shift_end=end,
                         status=WORKING, source=c.source, is_cover=True))
    return rows
