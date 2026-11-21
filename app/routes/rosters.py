import csv
import io
from datetime import date

from flask import (Blueprint, Response, abort, current_app, flash, jsonify, redirect,
                   render_template, request, url_for)

from app.extensions import db
from app.models import (Availability, Brand, Conflict, Employee, Pod, Process, RosterChangeLog,
                        RosterVersion)
from app.scheduling import service
from app.scheduling.service import RosterError
from app.scheduling.views import STATUS_CODE, RosterView
from app.services.ai_explainer import explain

rosters_bp = Blueprint("rosters", __name__, url_prefix="/rosters")

EDITABLE_STATUSES = ["WORKING", "WEEKLY_OFF", "LEAVE", "COMP_OFF", "UNAVAILABLE", "PUBLIC_HOLIDAY"]
MONTHS = [(i, date(2000, i, 1).strftime("%B")) for i in range(1, 13)]


def _version(version_id):
    return db.get_or_404(RosterVersion, version_id)


def _date(raw, field="date"):
    try:
        return date.fromisoformat((raw or "").strip())
    except ValueError:
        raise RosterError(f"Enter a valid {field}.")


def _back(version, **extra):
    args = {k: v for k, v in request.form.items() if k.startswith("v_")}
    params = {k[2:]: v for k, v in args.items() if v}
    params.update(extra)
    return redirect(url_for("rosters.detail", version_id=version.id, **params))


@rosters_bp.route("/")
def index():
    versions = RosterVersion.query.order_by(RosterVersion.roster_month.desc(),
                                            RosterVersion.version_number.desc()).all()
    counts = {v.id: service.conflict_counts(v.id) for v in versions}
    today = date.today()
    return render_template("rosters/index.html", versions=versions, counts=counts, months=MONTHS,
                           current_month=today.month, current_year=today.year)


@rosters_bp.post("/generate")
def generate():
    try:
        year = int(request.form.get("year", ""))
        month = int(request.form.get("month", ""))
        if not 2020 <= year <= 2100 or not 1 <= month <= 12:
            raise RosterError("Select a valid month and year.")
        version = service.generate_roster(year, month, notes=request.form.get("notes") or "Generated from dashboard")
        c = service.conflict_counts(version.id)
        flash(f"{version.label} generated: {c['errors']} error(s), {c['warnings']} warning(s). "
              "Review the conflicts before publishing.", "success" if not c["errors"] else "warning")
        return redirect(url_for("rosters.detail", version_id=version.id))
    except (RosterError, ValueError) as error:
        flash(str(error), "error")
    return redirect(url_for("rosters.index"))


@rosters_bp.route("/<int:version_id>")
def detail(version_id):
    version = _version(version_id)
    view = request.args.get("view", "company")
    rv = RosterView(version)
    ctx = dict(version=version, rv=rv, view=view, summary=rv.summary(), status_codes=STATUS_CODE,
               editable_statuses=EDITABLE_STATUSES,
               log=RosterChangeLog.query.filter_by(roster_version_id=version.id)
               .order_by(RosterChangeLog.created_at.desc(), RosterChangeLog.id.desc()).limit(30).all(),
               siblings=RosterVersion.query.filter(RosterVersion.roster_month == version.roster_month,
                                                   RosterVersion.id != version.id)
               .order_by(RosterVersion.version_number.desc()).all())
    pods = rv.pods
    brands = sorted({rv.brands[b] for b, _ in rv.sc.pairs}, key=lambda b: b.name)
    processes = sorted({rv.processes[p] for _, p in rv.sc.pairs}, key=lambda p: p.code)
    ctx.update(pods=pods, brands=brands, processes=processes,
               employees=sorted(rv.employees.values(), key=lambda e: e.full_name))

    if view == "pod":
        pod_id = request.args.get("pod_id", type=int) or (pods[0].id if pods else None)
        ctx.update(pod_id=pod_id, groups=rv.pod_groups(pod_id))
    elif view == "brand":
        brand_id = request.args.get("brand_id", type=int)
        ctx.update(brand_id=brand_id, coverage=rv.coverage_rows(brand_id=brand_id))
        if brand_id:
            emp_ids = {e for (b, p) in rv.sc.pairs if b == brand_id
                       for e in rv.sc.primaries(b, p, rv.days[0]) + rv.sc.backups(b, p, rv.days[0])}
            ctx["emp_rows"] = rv.employee_rows(sorted(emp_ids, key=lambda i: rv.sc.emp_name(i)))
    elif view == "process":
        process_id = request.args.get("process_id", type=int) or (processes[0].id if processes else None)
        emp_ids = {e for (b, p) in rv.sc.pairs if p == process_id for e in rv.sc.primaries(b, p, rv.days[0])}
        ctx.update(process_id=process_id, coverage=rv.coverage_rows(process_id=process_id),
                   emp_rows=rv.employee_rows(sorted(emp_ids, key=lambda i: rv.sc.emp_name(i))))
    elif view == "employee":
        emp_id = request.args.get("employee_id", type=int) or (ctx["employees"][0].id if ctx["employees"] else None)
        ctx.update(employee_id=emp_id, employee=rv.employees.get(emp_id),
                   emp_days=rv.employee_detail(emp_id) if emp_id else [],
                   emp_row=(rv.employee_rows([emp_id]) or [None])[0])
    elif view == "day":
        try:
            day = date.fromisoformat(request.args.get("date", ""))
        except ValueError:
            day = date.today() if rv.days[0] <= date.today() <= rv.days[-1] else rv.days[0]
        day = min(max(day, rv.days[0]), rv.days[-1])
        ctx.update(day=day, day_info=rv.day_detail(day))
    elif view == "conflicts":
        severity = request.args.get("severity", "")
        ctype = request.args.get("type", "")
        items = [c for c in rv.conflicts if (not severity or c.severity == severity)
                 and (not ctype or c.conflict_type == ctype)]
        ctx.update(severity=severity, ctype=ctype, items=items,
                   types=sorted({c.conflict_type for c in rv.conflicts}))
    else:
        ctx.update(view="company", groups=rv.pod_groups(), coverage=rv.coverage_rows())
    return render_template("rosters/detail.html", **ctx)


# ------------------------------------------------------------------ editing
@rosters_bp.post("/<int:version_id>/day")
def edit_day(version_id):
    version = _version(version_id)
    try:
        employee_id = request.form.get("employee_id", type=int)
        day = _date(request.form.get("date"))
        status = request.form.get("status", "")
        if status not in EDITABLE_STATUSES:
            raise RosterError("Choose a valid status.")
        before = service.conflict_counts(version.id)
        service.set_day_status(version, employee_id, day, status, request.form.get("note", "").strip()[:200])
        after = service.conflict_counts(version.id)
        delta = after["errors"] - before["errors"]
        impact = ("no change in errors" if delta == 0 else
                  f"{delta} new error(s) – see highlighted cells" if delta > 0 else f"{-delta} error(s) resolved")
        flash(f"Saved and re-validated: {impact} (now {after['errors']} errors, {after['warnings']} warnings).",
              "warning" if delta > 0 else "success")
    except RosterError as error:
        flash(str(error), "error")
    return _back(version)


@rosters_bp.post("/<int:version_id>/cover")
def add_cover(version_id):
    version = _version(version_id)
    try:
        service.add_cover(version, request.form.get("employee_id", type=int), request.form.get("brand_id", type=int),
                          request.form.get("process_id", type=int), _date(request.form.get("date")))
        flash(f"Cover assigned and roster re-validated ({service.conflict_counts(version.id)['errors']} errors left).",
              "success")
    except RosterError as error:
        flash(str(error), "error")
    return _back(version)


@rosters_bp.post("/<int:version_id>/cover/<int:entry_id>/delete")
def remove_cover(version_id, entry_id):
    version = _version(version_id)
    try:
        service.remove_cover(version, entry_id)
        flash("Cover removed and roster re-validated.", "success")
    except RosterError as error:
        flash(str(error), "error")
    return _back(version)


@rosters_bp.post("/<int:version_id>/auto-cover")
def auto_cover(version_id):
    version = _version(version_id)
    try:
        applied = service.auto_assign_covers(version)
        c = service.conflict_counts(version.id)
        flash(f"Applied {len(applied)} suggested cover(s). {c['errors']} error(s) still need a decision."
              if applied else "No compatible cover candidates for the remaining gaps.", "success" if applied else "warning")
    except RosterError as error:
        flash(str(error), "error")
    return _back(version, view="conflicts")


@rosters_bp.post("/<int:version_id>/revalidate")
def revalidate(version_id):
    version = _version(version_id)
    service.revalidate(version)
    c = service.conflict_counts(version.id)
    flash(f"Re-validated against the current rules and leave: {c['errors']} error(s), {c['warnings']} warning(s).",
          "success")
    return _back(version)


@rosters_bp.post("/<int:version_id>/publish")
def publish(version_id):
    version = _version(version_id)
    try:
        service.publish(version, acknowledge_errors=request.form.get("acknowledge") == "on")
        flash(f"{version.label} published. Any previously published version of this month was archived.", "success")
    except RosterError as error:
        flash(str(error), "error")
    return redirect(url_for("rosters.detail", version_id=version.id))


@rosters_bp.post("/<int:version_id>/revise")
def revise(version_id):
    version = _version(version_id)
    new = service.create_revision(version, request.form.get("reason") or "Manual revision")
    flash(f"Draft {new.label} created from V{version.version_number}. Edits apply to the draft only.", "success")
    return redirect(url_for("rosters.detail", version_id=new.id))


@rosters_bp.post("/<int:version_id>/reoptimise")
def reoptimise(version_id):
    version = _version(version_id)
    try:
        start = _date(request.form.get("from_date"), "start date")
        if not version.roster_month <= start <= service.scenario_for(version).end:
            raise RosterError("The start date must be inside the roster month.")
        new = service.reoptimise(version, start)
        before, after = service.conflict_counts(version.id), service.conflict_counts(new.id)
        flash(f"Re-optimised from {start:%d %b} as {new.label}: errors {before['errors']} → {after['errors']}. "
              "Past days and manual edits were kept.", "success")
        return redirect(url_for("rosters.detail", version_id=new.id))
    except RosterError as error:
        flash(str(error), "error")
        return redirect(url_for("rosters.detail", version_id=version.id))


@rosters_bp.post("/<int:version_id>/delete")
def delete(version_id):
    version = _version(version_id)
    try:
        label = version.label
        service.delete_version(version)
        flash(f"{label} deleted.", "success")
    except RosterError as error:
        flash(str(error), "error")
        return redirect(url_for("rosters.detail", version_id=version_id))
    return redirect(url_for("rosters.index"))


@rosters_bp.post("/conflicts/<int:conflict_id>/acknowledge")
def acknowledge(conflict_id):
    conflict = db.get_or_404(Conflict, conflict_id)
    service.acknowledge(conflict, not conflict.resolved)
    flash("Conflict acknowledged." if conflict.resolved else "Conflict re-opened.", "success")
    return _back(conflict.version, view="conflicts")


@rosters_bp.post("/conflicts/<int:conflict_id>/explain")
def explain_conflict(conflict_id):
    conflict = db.get_or_404(Conflict, conflict_id)
    text, source = explain(conflict)
    if source == "claude":
        conflict.ai_explanation = text
        db.session.commit()
    return jsonify(explanation=text, source=source)


# ------------------------------------------------------------------ compare & export
@rosters_bp.route("/<int:version_id>/compare")
def compare(version_id):
    version = _version(version_id)
    other = db.get_or_404(RosterVersion, request.args.get("other", type=int) or 0)
    if other.roster_month != version.roster_month:
        abort(400)
    diff = service.compare_versions(other, version)
    names = {e.id: e.full_name for e in Employee.query.all()}
    brands = {b.id: b.name for b in Brand.query.all()}
    processes = {p.id: p.code for p in Process.query.all()}
    return render_template("rosters/compare.html", version=version, other=other, diff=diff, names=names,
                           brands=brands, processes=processes,
                           counts=(service.conflict_counts(other.id), service.conflict_counts(version.id)))


@rosters_bp.route("/<int:version_id>/export.csv")
def export(version_id):
    version = _version(version_id)
    kind = request.args.get("kind", "grid")
    rv = RosterView(version)
    out = io.StringIO()
    w = csv.writer(out)
    if kind == "entries":
        w.writerow(["date", "employee_code", "employee", "pod", "brand", "process", "shift_start", "shift_end",
                    "type", "source"])
        rows = sorted((e for lst in list(rv.duties.values()) + list(rv.covers.values()) for e in lst),
                      key=lambda e: (e.roster_date, e.employee.full_name, e.brand.name))
        for e in rows:
            w.writerow([e.roster_date, e.employee.employee_code, e.employee.full_name,
                        e.employee.pod.name if e.employee.pod else "", e.brand.name, e.process.code,
                        f"{e.shift_start:%H:%M}", f"{e.shift_end:%H:%M}", "COVER" if e.is_cover else "PRIMARY",
                        e.source])
    elif kind == "conflicts":
        w.writerow(["date", "severity", "type", "brand", "process", "employee", "required", "available",
                    "message", "suggestion", "acknowledged"])
        for c in rv.conflicts:
            w.writerow([c.roster_date, c.severity, c.conflict_type, c.brand.name if c.brand else "",
                        c.process.code if c.process else "", c.employee.full_name if c.employee else "",
                        c.required_staff, c.available_staff, c.message, c.suggestion or "", c.resolved])
    else:
        kind = "grid"
        w.writerow(["employee_code", "employee", "pod"] + [d.isoformat() for d in rv.days])
        for group in rv.pod_groups():
            for row in group["rows"]:
                w.writerow([row["employee"].employee_code, row["employee"].full_name,
                            group["pod"].name if group["pod"] else ""] + [c["code"] if c else "" for c in row["cells"]])
    filename = f"roster-{version.roster_month:%Y-%m}-v{version.version_number}-{kind}.csv"
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={filename}"})


# ------------------------------------------------------------------ change impact (what-if)
@rosters_bp.route("/impact", methods=["GET"])
def impact():
    versions = RosterVersion.query.filter(RosterVersion.status != "ARCHIVED").order_by(
        RosterVersion.roster_month.desc(), RosterVersion.version_number.desc()).all()
    employees = Employee.query.filter_by(active=True).order_by(Employee.full_name).all()
    result, version, error = None, None, None
    record = db.session.get(Availability, request.args.get("availability_id", type=int) or 0)
    employee_id = request.args.get("employee_id", type=int) or (record.employee_id if record else None)
    start = request.args.get("start") or (record.start_date.isoformat() if record else "")
    end = request.args.get("end") or (record.end_date.isoformat() if record else "")
    kind = request.args.get("kind") or (record.availability_type if record else "UNAVAILABLE")
    version_id = request.args.get("version_id", type=int)
    if employee_id and start:
        try:
            s = date.fromisoformat(start)
            e = date.fromisoformat(end) if end else s
            if e < s:
                raise RosterError("End date is before the start date.")
            version = db.session.get(RosterVersion, version_id) if version_id else service.latest_version_for(s)
            if not version:
                raise RosterError("No roster exists for that month yet – generate one first.")
            result = service.impact_of_absence(version, employee_id, s, e, kind)
        except (RosterError, ValueError) as exc:
            error = str(exc)
    return render_template("rosters/impact.html", versions=versions, employees=employees, result=result,
                           version=version, error=error, employee_id=employee_id, start=start, end=end, kind=kind,
                           record=record)


@rosters_bp.post("/impact/apply")
def impact_apply():
    version = _version(request.form.get("version_id", type=int) or 0)
    try:
        target = service.apply_absence(version, request.form.get("employee_id", type=int),
                                       _date(request.form.get("start")), _date(request.form.get("end")),
                                       request.form.get("kind", "UNAVAILABLE"), request.form.get("note", ""))
        c = service.conflict_counts(target.id)
        msg = (f"Change applied to {target.label}"
               + (" (new draft revision – the published roster stays live until you publish this one)"
                  if target.id != version.id else "")
               + f". {c['errors']} error(s) to review; use the suggested covers or 'Auto-assign covers'.")
        flash(msg, "warning" if c["errors"] else "success")
        return redirect(url_for("rosters.detail", version_id=target.id, view="conflicts"))
    except RosterError as error:
        flash(str(error), "error")
        return redirect(url_for("rosters.impact"))
