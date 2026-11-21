"""Turn a stored roster version into the data the roster screens render."""
from collections import defaultdict

from app.models import Brand, Conflict, Employee, Pod, Process, RosterDay, RosterEntry
from .service import scenario_for

STATUS_CODE = {
    "WORKING": ("W", "st-work"), "WEEKLY_OFF": ("WO", "st-off"), "PUBLIC_HOLIDAY": ("PH", "st-hol"),
    "LEAVE": ("L", "st-leave"), "COMP_OFF": ("CO", "st-comp"), "UNAVAILABLE": ("UA", "st-unav"),
    "UNASSIGNED": ("–", "st-none"),
}


class RosterView:
    def __init__(self, version):
        self.version = version
        self.sc = sc = scenario_for(version)
        self.days = sc.days
        self.holidays = sc.holidays
        self.day_rows = {(d.employee_id, d.roster_date): d
                         for d in RosterDay.query.filter_by(roster_version_id=version.id).all()}
        emp_ids = {k[0] for k in self.day_rows}
        self.employees = {e.id: e for e in Employee.query.filter(Employee.id.in_(emp_ids)).all()} if emp_ids else {}
        self.brands = {b.id: b for b in Brand.query.all()}
        self.processes = {p.id: p for p in Process.query.all()}
        self.pods = Pod.query.order_by(Pod.name).all()

        self.duties = defaultdict(list)   # (emp, day) -> [entry]
        self.covers = defaultdict(list)   # (emp, day) -> [entry]
        self.scope_staff = defaultdict(list)  # (b, p, day) -> [(entry)]
        for e in RosterEntry.query.filter_by(roster_version_id=version.id).all():
            (self.covers if e.is_cover else self.duties)[(e.employee_id, e.roster_date)].append(e)
            self.scope_staff[(e.brand_id, e.process_id, e.roster_date)].append(e)

        self.conflicts = (Conflict.query.filter_by(roster_version_id=version.id)
                          .order_by(Conflict.roster_date, Conflict.severity, Conflict.id).all())
        self.emp_issues = defaultdict(list)
        self.scope_issues = defaultdict(list)
        for c in self.conflicts:
            if c.employee_id:
                self.emp_issues[(c.employee_id, c.roster_date)].append(c)
            if c.brand_id:
                self.scope_issues[(c.brand_id, c.process_id, c.roster_date)].append(c)

    # ---------------------------------------------------------------- employee grid
    def cell(self, emp_id, day):
        row = self.day_rows.get((emp_id, day))
        if row is None:
            return None
        code, css = STATUS_CODE.get(row.status, (row.status[:2], ""))
        duties = self.duties.get((emp_id, day), [])
        covers = self.covers.get((emp_id, day), [])
        issues = [c for c in self.emp_issues.get((emp_id, day), []) if c.severity != "INFO"]
        title = [f"{self.employees[emp_id].full_name} · {day:%a %d %b}", row.status.replace("_", " ").title()]
        if row.note:
            title.append(row.note)
        title += [f"• {e.brand.name} / {e.process.code} {e.shift_start:%H:%M}-{e.shift_end:%H:%M}" for e in duties]
        title += [f"• COVER {e.brand.name} / {e.process.code}" for e in covers]
        title += [f"⚠ {c.message}" for c in issues]
        return dict(code=code + ("+" if covers else ""), css=css, manual=row.source == "MANUAL",
                    issue=bool(issues), title="\n".join(title), status=row.status, note=row.note or "")

    def employee_rows(self, emp_ids):
        rows = []
        for emp_id in emp_ids:
            emp = self.employees.get(emp_id)
            if not emp:
                continue
            cells = [self.cell(emp_id, d) for d in self.days]
            counts = defaultdict(int)
            for c in cells:
                if c:
                    counts[c["status"]] += 1
            rows.append(dict(employee=emp, cells=cells, worked=counts["WORKING"],
                             off=counts["WEEKLY_OFF"] + counts["PUBLIC_HOLIDAY"],
                             leave=counts["LEAVE"] + counts["COMP_OFF"] + counts["UNAVAILABLE"]))
        return rows

    def pod_groups(self, pod_id=None):
        groups = []
        by_pod = defaultdict(list)
        for emp in self.employees.values():
            by_pod[emp.pod_id].append(emp)
        for pod in self.pods:
            if pod_id and pod.id != pod_id:
                continue
            members = sorted(by_pod.get(pod.id, []), key=lambda e: (e.id != pod.lead_employee_id, e.full_name))
            if members:
                groups.append(dict(pod=pod, lead=pod.lead_employee, rows=self.employee_rows([e.id for e in members])))
        if not pod_id and by_pod.get(None):
            groups.append(dict(pod=None, lead=None, rows=self.employee_rows(
                [e.id for e in sorted(by_pod[None], key=lambda e: e.full_name)])))
        return groups

    # ---------------------------------------------------------------- coverage grid
    def coverage_rows(self, brand_id=None, process_id=None):
        rows = []
        pairs = sorted(self.sc.pairs, key=lambda bp: (self.brands[bp[0]].name, self.processes[bp[1]].code))
        for b, p in pairs:
            if (brand_id and b != brand_id) or (process_id and p != process_id):
                continue
            cells = []
            gaps = 0
            for d in self.days:
                need = self.sc.demand(b, p, d)
                staff = self.scope_staff.get((b, p, d), [])
                have = len(staff)
                if need <= 0:
                    css, label = "cv-closed", ""
                    tip = f"Closed: {self.sc.closed_reason(b, p, d)}"
                else:
                    if have < need:
                        css = "cv-gap"
                        gaps += 1
                    elif any(e.is_cover for e in staff):
                        css = "cv-cover"
                    else:
                        css = "cv-ok"
                    label = f"{have}/{need}"
                    names = ", ".join(e.employee.full_name + (" (cover)" if e.is_cover else "") for e in staff)
                    tip = f"{d:%a %d %b}: {have} of {need} required. {names or 'Nobody working'}"
                override = self.sc.overrides.get((b, p, d))
                if override:
                    tip += f" · Override: {override[1]}"
                cells.append(dict(css=css, label=label, title=tip, day=d))
            rule = self.sc.rule_for(b, p, self.days[0])
            primaries = self.sc.primaries(b, p, self.days[0])
            rows.append(dict(brand=self.brands[b], process=self.processes[p], cells=cells, gaps=gaps,
                             rule=rule, staffing=len(primaries),
                             people=[self.sc.emp_name(e) for e in primaries],
                             backups=[self.sc.emp_name(e) for e in self.sc.backups(b, p, self.days[0])]))
        return rows

    # ---------------------------------------------------------------- day view
    def day_detail(self, day):
        scopes = []
        for row in self.coverage_rows():
            b, p = row["brand"].id, row["process"].id
            need = self.sc.demand(b, p, day)
            if need <= 0:
                continue
            staff = self.scope_staff.get((b, p, day), [])
            scopes.append(dict(brand=row["brand"], process=row["process"], need=need, staff=staff,
                               ok=len(staff) >= need, issues=self.scope_issues.get((b, p, day), [])))
        off = []
        for emp_id, emp in sorted(self.employees.items(), key=lambda kv: kv[1].full_name):
            r = self.day_rows.get((emp_id, day))
            if r and r.status != "WORKING":
                off.append(dict(employee=emp, status=r.status, note=r.note))
        working = [self.employees[e] for (e, d), r in self.day_rows.items() if d == day and r.status == "WORKING"]
        return dict(scopes=scopes, off=off, working=sorted(working, key=lambda e: e.full_name))

    def employee_detail(self, emp_id):
        out = []
        for d in self.days:
            r = self.day_rows.get((emp_id, d))
            out.append(dict(day=d, row=r, duties=self.duties.get((emp_id, d), []),
                            covers=self.covers.get((emp_id, d), []),
                            issues=self.emp_issues.get((emp_id, d), []),
                            holiday=self.holidays.get(d)))
        return out

    def summary(self):
        total_scope_days = sum(1 for (b, p) in self.sc.pairs for d in self.days if self.sc.demand(b, p, d) > 0)
        gap_days = sum(1 for c in self.conflicts if c.conflict_type in ("COVERAGE_GAP", "UNASSIGNED_REQUIREMENT"))
        return dict(
            employees=len(self.employees), scopes=len(self.sc.pairs), scope_days=total_scope_days,
            covered_pct=round(100 * (total_scope_days - gap_days) / total_scope_days, 1) if total_scope_days else 100,
            errors=sum(1 for c in self.conflicts if c.severity == "ERROR"),
            open_errors=sum(1 for c in self.conflicts if c.severity == "ERROR" and not c.resolved),
            warnings=sum(1 for c in self.conflicts if c.severity == "WARNING"),
            info=sum(1 for c in self.conflicts if c.severity == "INFO"),
            covers=sum(len(v) for v in self.covers.values()),
        )
