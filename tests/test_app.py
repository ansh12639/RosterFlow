"""Integration tests: seed data, generation, views, edits and change handling."""
from datetime import date

from app.extensions import db
from app.models import (Assignment, Availability, Brand, Conflict, Employee, Pod, RosterDay,
                        RosterEntry, RosterVersion)
from app.scheduling import service


def _dec(app):
    return RosterVersion.query.filter_by(roster_month=date(2026, 12, 1)).first()


def test_seed_matches_assessment_staffing_pattern(seeded):
    assert Employee.query.count() >= 30
    assert Pod.query.count() >= 3 and all(p.lead_employee_id for p in Pod.query.all())
    brands = Brand.query.all()
    single = [b for b in brands if len(b.primary_employee_ids) == 1]
    multi = [b for b in brands if len(b.primary_employee_ids) > 1]
    assert 0.75 <= len(single) / len(brands) <= 0.85
    assert all(2 <= len(b.primary_employee_ids) <= 3 for b in multi)
    # shared process (two primaries on the same brand/process) and separate processes both present
    pairs = {}
    for a in Assignment.query.filter_by(priority=1).all():
        pairs.setdefault((a.brand_id, a.process_id), set()).add(a.employee_id)
    assert any(len(v) > 1 for v in pairs.values())
    # employees on multiple brands
    per_emp = {}
    for a in Assignment.query.filter_by(priority=1).all():
        per_emp.setdefault(a.employee_id, set()).add(a.brand_id)
    assert any(len(v) > 1 for v in per_emp.values())


def test_seed_generates_rosters_and_every_active_employee_is_rostered(seeded):
    published = RosterVersion.query.filter_by(status="PUBLISHED").one()
    draft = _dec(seeded)
    assert published.roster_month == date(2026, 11, 1) and draft.status == "DRAFT"
    days = RosterDay.query.filter_by(roster_version_id=draft.id).count()
    assert days == Employee.query.filter_by(active=True).count() * 31
    # the generator must never silently skip a gap: errors reported are real gaps
    sc = service.scenario_for(draft)
    plan = service.load_plan(draft)
    from app.scheduling.validator import validate
    assert len(validate(sc, plan)) == Conflict.query.filter_by(roster_version_id=draft.id).count()


def test_all_pages_render(seeded, client):
    draft = _dec(seeded)
    urls = ["/", "/health", "/employees/", "/catalog/", "/pods/", "/working-rules/", "/availability/",
            "/weekly-offs/", "/holidays/", "/rosters/", "/rosters/impact"]
    for view in ["company", "pod", "brand", "process", "employee", "day", "conflicts"]:
        urls.append(f"/rosters/{draft.id}?view={view}")
    brand = Brand.query.filter_by(name="GlowVeda").one()
    urls += [f"/rosters/{draft.id}?view=brand&brand_id={brand.id}", f"/rosters/{draft.id}?view=day&date=2026-12-25",
             f"/rosters/{draft.id}?view=conflicts&severity=ERROR"]
    for kind in ["grid", "entries", "conflicts"]:
        urls.append(f"/rosters/{draft.id}/export.csv?kind={kind}")
    for url in urls:
        response = client.get(url)
        assert response.status_code == 200, url
    assert client.get("/nope").status_code == 404


def test_manual_edit_revalidates_and_reports_new_gap(seeded, client):
    draft = _dec(seeded)
    owner = Employee.query.filter_by(full_name="Ritu Agarwal").one()  # single-resource Mon–Sat brand
    day = date(2026, 12, 9)
    assert RosterDay.query.filter_by(roster_version_id=draft.id, employee_id=owner.id, roster_date=day).one().status == "WORKING"
    res = client.post(f"/rosters/{draft.id}/day", data=dict(employee_id=owner.id, date=day.isoformat(),
                                                            status="UNAVAILABLE", v_view="company"))
    assert res.status_code == 302
    gaps = Conflict.query.filter_by(roster_version_id=draft.id, conflict_type="COVERAGE_GAP", roster_date=day).all()
    assert any("Silk & Thread" in g.message for g in gaps)
    assert RosterDay.query.filter_by(roster_version_id=draft.id, employee_id=owner.id, roster_date=day).one().source == "MANUAL"


def test_add_cover_resolves_gap(seeded, client):
    draft = _dec(seeded)
    service.auto_assign_covers(draft)
    owner = Employee.query.filter_by(full_name="Ritu Agarwal").one()
    day = date(2026, 12, 9)
    service.set_day_status(draft, owner.id, day, "UNAVAILABLE", "sick")
    gap = Conflict.query.filter_by(roster_version_id=draft.id, conflict_type="COVERAGE_GAP", roster_date=day).filter(
        Conflict.message.contains("Silk & Thread / Customer Support")).one()
    assert gap.candidates, "a same-pod colleague who knows CS should be suggested"
    cand = gap.candidates[0]
    client.post(f"/rosters/{draft.id}/cover", data=dict(employee_id=cand["employee_id"], brand_id=gap.brand_id,
                                                        process_id=gap.process_id, date=day.isoformat()))
    still = Conflict.query.filter_by(roster_version_id=draft.id, conflict_type="COVERAGE_GAP", roster_date=day,
                                     brand_id=gap.brand_id, process_id=gap.process_id).count()
    assert still == 0
    assert RosterEntry.query.filter_by(roster_version_id=draft.id, is_cover=True, roster_date=day,
                                       employee_id=cand["employee_id"]).count() == 1


def test_publish_blocked_by_errors_unless_acknowledged(seeded, client):
    draft = _dec(seeded)
    assert service.conflict_counts(draft.id)["open_errors"] > 0
    client.post(f"/rosters/{draft.id}/publish", data={})
    assert db.session.get(RosterVersion, draft.id).status == "DRAFT"
    client.post(f"/rosters/{draft.id}/publish", data={"acknowledge": "on"})
    assert db.session.get(RosterVersion, draft.id).status == "PUBLISHED"


def test_change_after_publication_creates_revision_and_flags_gap(seeded, client):
    published = RosterVersion.query.filter_by(status="PUBLISHED").one()
    owner = Employee.query.filter_by(full_name="Manoj Patil").one()  # runs all processes of Crisp Snacks
    day = date(2026, 11, 25)
    impact = service.impact_of_absence(published, owner.id, day, day, "UNAVAILABLE")
    assert impact["gaps"] >= 1 and all(r["single"] for r in impact["rows"] if r["scope"].startswith("Crisp"))
    res = client.post("/rosters/impact/apply", data=dict(version_id=published.id, employee_id=owner.id,
                                                         start=day.isoformat(), end=day.isoformat(),
                                                         kind="UNAVAILABLE", note="Sick"))
    assert res.status_code == 302
    assert db.session.get(RosterVersion, published.id).status == "PUBLISHED"  # live roster untouched
    revision = RosterVersion.query.filter_by(parent_version_id=published.id).one()
    assert revision.status == "DRAFT"
    assert Conflict.query.filter_by(roster_version_id=revision.id, conflict_type="COVERAGE_GAP", roster_date=day) \
        .filter(Conflict.message.contains("Crisp Snacks")).count() == 3


def test_shared_brand_absorbs_one_absence(seeded):
    draft = _dec(seeded)
    yash = Employee.query.filter_by(full_name="Lakshmi Reddy").one()  # HomeHaven CS shared by two
    day = date(2026, 12, 9)  # Wednesday: Deepak has a FIXED Wednesday off, so no -> pick Thursday
    day = date(2026, 12, 10)
    impact = service.impact_of_absence(draft, yash.id, day, day)
    rows = [r for r in impact["rows"] if r["scope"].startswith("HomeHaven")]
    assert rows and rows[0]["ok"], "remaining HomeHaven CS staff should absorb a single absence on a min-1 day"


def test_pending_leave_approval_redirects_to_impact(seeded, client):
    pending = Availability.query.filter_by(approval_status="PENDING").first()
    res = client.post(f"/availability/{pending.id}/status", data={"approval_status": "APPROVED"})
    assert res.status_code == 302 and "/rosters/impact" in res.headers["Location"]
    page = client.get(res.headers["Location"])
    assert b"impact on" in page.data


def test_reoptimise_respects_manual_edits_and_new_leave(seeded):
    draft = _dec(seeded)
    emp = Employee.query.filter_by(full_name="Pooja Bhat").one()
    service.set_day_status(draft, emp.id, date(2026, 12, 18), "WEEKLY_OFF", "swap")
    pending = Availability.query.filter_by(approval_status="PENDING").first()
    pending.approval_status = "APPROVED"
    db.session.commit()
    new = service.reoptimise(draft, date(2026, 12, 15))
    cell = RosterDay.query.filter_by(roster_version_id=new.id, employee_id=emp.id, roster_date=date(2026, 12, 18)).one()
    assert cell.status == "WEEKLY_OFF" and cell.source == "MANUAL"
    leave_day = RosterDay.query.filter_by(roster_version_id=new.id, employee_id=pending.employee_id,
                                          roster_date=pending.start_date).one()
    assert leave_day.status == "LEAVE" or pending.start_date < date(2026, 12, 15)


def test_rule_change_is_picked_up_by_revalidation(seeded, client):
    draft = _dec(seeded)
    from app.models import WorkingRule, Process
    brand = Brand.query.filter_by(name="Silk & Thread").one()
    cs = Process.query.filter_by(code="CS").one()
    rule = WorkingRule.query.filter_by(brand_id=brand.id, process_id=cs.id).one()
    rule.minimums = (1, 1, 1, 1, 1, 1, 1)  # brand now needs Sunday coverage
    db.session.commit()
    client.post(f"/rosters/{draft.id}/revalidate", data={})
    sundays = Conflict.query.filter_by(roster_version_id=draft.id, brand_id=brand.id, conflict_type="COVERAGE_GAP").all()
    assert sundays and all(c.roster_date.weekday() == 6 for c in sundays)


def test_explain_conflict_falls_back_without_api_key(seeded, client):
    conflict = Conflict.query.filter_by(conflict_type="COVERAGE_GAP").first()
    data = client.post(f"/rosters/conflicts/{conflict.id}/explain").get_json()
    assert data["source"] == "rules" and data["explanation"]


def test_configuration_crud_flows(seeded, client):
    brand = Brand.query.first()
    from app.models import Process
    proc = Process.query.first()
    assert client.post("/catalog/brands/add", data={"name": "New Brand"}).status_code == 302
    new_brand = Brand.query.filter_by(name="New Brand").one()
    client.post("/working-rules/add", data=dict(brand_id=new_brand.id, process_id=proc.id, preset="CUSTOM",
                                                **{f"min_{i}": v for i, v in enumerate([2, 1, 1, 1, 1, 0, 0])},
                                                shift_start="09:00", shift_end="18:00", effective_from="2026-01-01"))
    from app.models import WorkingRule
    rule = WorkingRule.query.filter_by(brand_id=new_brand.id).one()
    assert rule.minimums == (2, 1, 1, 1, 1, 0, 0) and rule.operating_days_label == "Mon–Fri"
    emp = Employee.query.first()
    client.post("/pods/assignments/add", data=dict(employee_id=emp.id, brand_id=new_brand.id, process_id=proc.id,
                                                   effective_from="2026-01-01", priority=1))
    assert Assignment.query.filter_by(brand_id=new_brand.id).count() == 1
    client.post("/weekly-offs/add", data=dict(employee_id=emp.id, weekday=2, kind="FIXED", effective_from="2026-01-01"))
    client.post("/working-rules/overrides/add", data=dict(brand_id=brand.id, process_id=proc.id,
                                                          override_date="2026-12-31", minimum_staff=3, reason="NYE"))
    version = service.generate_roster(2026, 12)
    assert version.version_number >= 2
