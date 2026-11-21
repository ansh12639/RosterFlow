"""Monthly roster generator.

Approach (deterministic, explainable heuristic rather than a black-box solver):

1. **Hard availability** – approved leave / comp-off / unavailability, FIXED weekly
   offs, days on which none of an employee's brands operate, and manager-locked
   (manual) cells are fixed first.
2. **Mandatory weekly rest** – every employee gets ``weekly_offs`` rest days per
   Mon–Sun week. Off days are placed greedily, most-constrained employee first,
   choosing the day that costs least:
       gap the off would create with no backup available  -> 1000
       gap, but a colleague who knows the process works ->  300
       gap the off would create but a backup is working   ->  100
       day is not the employee's PREFERRED off             ->   10
       small fairness terms (spread offs, rotate Sundays)  ->  < 5
   So a required client coverage day always beats a preferred weekly off.
3. **Repair** – for every remaining gap, try to move an auto-placed off of an
   assigned employee to another day of the same week that creates no gap.
4. **Backup covers** – remaining gaps are filled by *designated backups* who are
   working that day, have spare capacity and a compatible shift.
5. Anything still uncovered is left visible: the validator reports it with the
   reasons and ranked resolution candidates. The engine never hides a gap.
"""
from __future__ import annotations

from collections import defaultdict

from .plan import Cover, DayState, Plan
from .scenario import (ABSENCE_STATUS, PUBLIC_HOLIDAY, REST_STATUSES, UNASSIGNED,
                       WEEKDAYS, WEEKLY_OFF, WORKING)

COST_GAP_NO_BACKUP = 1000
COST_GAP_COLLEAGUE = 300  # someone working that day knows the process (manager can assign as cover)
COST_GAP_WITH_BACKUP = 100
COST_NOT_PREFERRED = 10


class RosterEngine:
    def __init__(self, scenario):
        self.sc = scenario

    # ------------------------------------------------------------------ public
    def generate(self, locked=None, keep_covers=()):
        """Build a Plan.

        ``locked``: {(employee_id, date): DayState} cells the engine must keep
        (manual edits, or past days when re-optimising mid-month).
        ``keep_covers``: covers to carry over unchanged.
        """
        sc = self.sc
        self.locked = dict(locked or {})
        self.plan = Plan(covers=list(keep_covers))
        self.auto_offs = set()
        self.offs_on_day = defaultdict(int)
        self.sunday_offs = defaultdict(int)

        self._base_statuses()
        self._init_coverage()
        for week in sc.weeks():
            self._place_weekly_offs(week)
        self._repair_gaps()
        self._assign_backup_covers()
        return self.plan

    # ------------------------------------------------------------------ steps
    def _base_statuses(self):
        sc = self.sc
        for emp in sc.active_employees.values():
            has_primary = sc.has_primary(emp.id)
            for day in sc.days:
                key = (emp.id, day)
                if key in self.locked:
                    self.plan.status[key] = self.locked[key]
                    continue
                absence = sc.absence(emp.id, day)
                if absence:
                    note = absence.note or absence.kind.replace("_", " ").title()
                    self.plan.status[key] = DayState(ABSENCE_STATUS[absence.kind], "AUTO", note)
                elif not has_primary:
                    self.plan.status[key] = DayState(UNASSIGNED, "AUTO", "No primary brand assignment")
                elif sc.fixed_off(emp.id, day):
                    self.plan.status[key] = DayState(WEEKLY_OFF, "AUTO", "Fixed weekly off")
                elif not sc.duties(emp.id, day):
                    if day in sc.holidays:
                        self.plan.status[key] = DayState(PUBLIC_HOLIDAY, "AUTO", sc.holidays[day])
                    else:
                        self.plan.status[key] = DayState(WEEKLY_OFF, "AUTO", "Assigned brands closed")
                else:
                    self.plan.status[key] = DayState(WORKING, "AUTO", "")

    def _init_coverage(self):
        self.cov = defaultdict(int)
        for (emp_id, day), state in self.plan.status.items():
            if state.status == WORKING:
                for b, p in self.sc.duties(emp_id, day):
                    self.cov[(b, p, day)] += 1
        for c in self.plan.covers:
            self.cov[(c.brand_id, c.process_id, c.day)] += 1

    def _set_off(self, emp_id, day, note):
        self.plan.status[(emp_id, day)] = DayState(WEEKLY_OFF, "AUTO", note)
        for b, p in self.sc.duties(emp_id, day):
            self.cov[(b, p, day)] -= 1
        self.auto_offs.add((emp_id, day))
        self.offs_on_day[day] += 1
        if day.weekday() == 6:
            self.sunday_offs[emp_id] += 1

    def _set_working(self, emp_id, day):
        self.plan.status[(emp_id, day)] = DayState(WORKING, "AUTO", "")
        for b, p in self.sc.duties(emp_id, day):
            self.cov[(b, p, day)] += 1
        self.auto_offs.discard((emp_id, day))
        self.offs_on_day[day] -= 1
        if day.weekday() == 6:
            self.sunday_offs[emp_id] -= 1

    def _backup_available(self, brand_id, process_id, day, exclude):
        for b in self.sc.backups(brand_id, process_id, day):
            if b != exclude and b in self.sc.active_employees and self.plan.is_working(b, day):
                return True
        return False

    def _colleague_available(self, brand_id, process_id, day, exclude):
        primaries = set(self.sc.primaries(brand_id, process_id, day))
        return any(e != exclude and e not in primaries and self.plan.is_working(e, day)
                   and self.sc.knows_process(e, process_id, day)
                   for e in self.sc.active_employees)

    def _gap_cost(self, emp_id, day):
        cost = 0
        for b, p in self.sc.duties(emp_id, day):
            if self.cov[(b, p, day)] - 1 < self.sc.demand(b, p, day):
                if self._backup_available(b, p, day, emp_id):
                    cost += COST_GAP_WITH_BACKUP
                elif self._colleague_available(b, p, day, emp_id):
                    cost += COST_GAP_COLLEAGUE
                else:
                    cost += COST_GAP_NO_BACKUP
        return cost

    def _off_cost(self, emp_id, day):
        cost = float(self._gap_cost(emp_id, day))
        preferred = self.sc.preferred_weekdays(emp_id, day)
        if preferred and day.weekday() not in preferred:
            cost += COST_NOT_PREFERRED
        # Fairness: spread offs across the week and rotate Sunday offs.
        cost += 0.3 * self.offs_on_day[day]
        if day.weekday() == 6 and not preferred:
            cost += 2 * self.sunday_offs[emp_id] - 1
        return cost

    def _candidates(self, emp_id, week):
        return [d for d in week if self.plan.status[(emp_id, d)].status == WORKING and (emp_id, d) not in self.locked]

    def _place_weekly_offs(self, week):
        sc = self.sc
        pending = {}
        for emp_id in sc.active_employees:
            if not sc.has_primary(emp_id):
                continue
            rest = sum(1 for d in week if self.plan.status[(emp_id, d)].status in REST_STATUSES)
            need = sc.required_offs(emp_id, week) - rest
            if need > 0:
                pending[emp_id] = need

        while pending:
            best = None
            for emp_id in list(pending):
                cands = self._candidates(emp_id, week)
                if not cands:
                    del pending[emp_id]  # nothing left to give (e.g. on leave all week)
                    continue
                scored = sorted((self._off_cost(emp_id, d), d) for d in cands)
                free_days = sum(1 for cost, _ in scored if cost < COST_GAP_WITH_BACKUP)
                key = (free_days, scored[0][0], emp_id)
                if best is None or key < best[0]:
                    best = (key, emp_id, scored[0])
            if best is None:
                break
            _, emp_id, (cost, day) = best
            self._set_off(emp_id, day, self._off_note(emp_id, day, cost))
            pending[emp_id] -= 1
            if pending[emp_id] <= 0:
                del pending[emp_id]

    def _off_note(self, emp_id, day, cost):
        preferred = self.sc.preferred_weekdays(emp_id, day)
        if preferred and day.weekday() in preferred:
            return "Preferred weekly off"
        if preferred:
            names = "/".join(WEEKDAYS[w][:3] for w in sorted(preferred))
            return f"Weekly off (moved from preferred {names} to protect coverage)"
        return "Weekly off (auto-placed)"

    def _repair_gaps(self):
        sc = self.sc
        weeks = sc.weeks()
        week_of = {d: w for w in weeks for d in w}
        for day in sc.days:
            for b, p in sc.pairs:
                if self.cov[(b, p, day)] >= sc.demand(b, p, day) or day not in week_of:
                    continue
                for emp_id in sc.primaries(b, p, day):
                    if (emp_id, day) not in self.auto_offs:
                        continue
                    previous_note = self.plan.status[(emp_id, day)].note
                    self._set_working(emp_id, day)
                    moved = False
                    for alt in sorted(self._candidates(emp_id, week_of[day]), key=lambda d: self._off_cost(emp_id, d)):
                        if alt != day and self._gap_cost(emp_id, alt) == 0:
                            self._set_off(emp_id, alt, self._off_note(emp_id, alt, self._off_cost(emp_id, alt)))
                            moved = True
                            break
                    if not moved:  # no gap-free alternative: rest stays where it was
                        self._set_off(emp_id, day, previous_note)
                    if self.cov[(b, p, day)] >= sc.demand(b, p, day):
                        break

    def _assign_backup_covers(self):
        sc = self.sc
        load = defaultdict(int)
        for c in self.plan.covers:
            load[(c.employee_id, c.day)] += 1
        for day in sc.days:
            for b, p in sc.pairs:
                need = sc.demand(b, p, day) - self.cov[(b, p, day)]
                if need <= 0:
                    continue
                for backup in sc.backups(b, p, day):
                    if need <= 0:
                        break
                    if backup not in sc.active_employees or not self.plan.is_working(backup, day):
                        continue
                    if (b, p) in sc.duties(backup, day) or load[(backup, day)] >= sc.max_covers_per_day:
                        continue
                    windows = [sc.shift(x, y, day) for x, y in sc.duties(backup, day)]
                    windows += [sc.shift(c.brand_id, c.process_id, day) for c in self.plan.covers
                                if c.employee_id == backup and c.day == day]
                    windows.append(sc.shift(b, p, day))
                    if sc.span_hours(windows) > sc.max_span_hours:
                        continue
                    self.plan.covers.append(Cover(backup, b, p, day, "AUTO"))
                    self.cov[(b, p, day)] += 1
                    load[(backup, day)] += 1
                    need -= 1
