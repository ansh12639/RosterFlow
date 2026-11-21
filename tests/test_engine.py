"""Unit tests for the pure scheduling core (no database)."""
from datetime import date, time

from app.scheduling.engine import RosterEngine
from app.scheduling.plan import Cover, DayState
from app.scheduling.scenario import (AbsenceIn, AssignmentIn, EmployeeIn, RuleIn, Scenario,
                                     WeeklyOffIn, WORKING, WEEKLY_OFF, LEAVE, PUBLIC_HOLIDAY)
from app.scheduling.validator import validate

ALL_WEEK = (1, 1, 1, 1, 1, 1, 1)
MON_SAT = (1, 1, 1, 1, 1, 1, 0)
DEC = dict(year=2026, month=12)  # 1 Dec 2026 is a Tuesday


def scenario(**kw):
    base = dict(employees=[], rules=[], assignments=[], brand_names={1: "Brand", 2: "Other"},
                process_names={10: "CS", 11: "ACC"}, **DEC)
    base.update(kw)
    return Scenario(**base)


def by_type(conflicts, kind):
    return [c for c in conflicts if c["conflict_type"] == kind]


def test_mon_sat_brand_single_owner_has_no_gaps_and_sunday_is_rest():
    sc = scenario(employees=[EmployeeIn(1, "Asha")],
                  rules=[RuleIn(1, 10, MON_SAT), RuleIn(1, 11, MON_SAT)],
                  assignments=[AssignmentIn(1, 1, 10), AssignmentIn(1, 1, 11)])
    plan = RosterEngine(sc).generate()
    assert plan.status[(1, date(2026, 12, 6))].status == WEEKLY_OFF  # Sunday
    assert plan.status[(1, date(2026, 12, 7))].status == WORKING
    conflicts = validate(sc, plan)
    assert not by_type(conflicts, "COVERAGE_GAP")
    assert not by_type(conflicts, "REST_VIOLATION")


def test_every_employee_gets_weekly_rest_even_on_7_day_brand_and_gap_is_flagged():
    sc = scenario(employees=[EmployeeIn(1, "Asha")], rules=[RuleIn(1, 10, ALL_WEEK)],
                  assignments=[AssignmentIn(1, 1, 10)])
    plan = RosterEngine(sc).generate()
    conflicts = validate(sc, plan)
    for week in sc.weeks():
        assert any(plan.status[(1, d)].status == WEEKLY_OFF for d in week)
    gaps = by_type(conflicts, "COVERAGE_GAP")
    assert len(gaps) == len(sc.weeks())  # one uncovered day per week, never silent
    assert "Single-resource" in gaps[0]["message"]


def test_backup_covers_single_owner_weekly_off():
    sc = scenario(employees=[EmployeeIn(1, "Asha", pod_id=1), EmployeeIn(2, "Ravi", pod_id=1)],
                  rules=[RuleIn(1, 10, ALL_WEEK), RuleIn(2, 10, MON_SAT)],
                  assignments=[AssignmentIn(1, 1, 10), AssignmentIn(2, 2, 10),
                               AssignmentIn(2, 1, 10, priority=2)])
    plan = RosterEngine(sc).generate()
    conflicts = validate(sc, plan)
    assert plan.covers, "backup should cover Asha's weekly offs"
    assert not by_type(conflicts, "COVERAGE_GAP")


def test_shared_process_staggers_offs_so_coverage_holds():
    sc = scenario(employees=[EmployeeIn(1, "A"), EmployeeIn(2, "B")], rules=[RuleIn(1, 10, ALL_WEEK)],
                  assignments=[AssignmentIn(1, 1, 10), AssignmentIn(2, 1, 10)])
    plan = RosterEngine(sc).generate()
    for d in sc.days:
        assert plan.is_working(1, d) or plan.is_working(2, d)
    assert not by_type(validate(sc, plan), "COVERAGE_GAP")


def test_coverage_beats_preferred_off_and_preference_violation_reported():
    # Both prefer Sunday; brand needs 1 person every day -> only one can have Sunday.
    sc = scenario(employees=[EmployeeIn(1, "A"), EmployeeIn(2, "B")], rules=[RuleIn(1, 10, ALL_WEEK)],
                  assignments=[AssignmentIn(1, 1, 10), AssignmentIn(2, 1, 10)],
                  weekly_offs=[WeeklyOffIn(1, 6), WeeklyOffIn(2, 6)])
    plan = RosterEngine(sc).generate()
    conflicts = validate(sc, plan)
    assert not by_type(conflicts, "COVERAGE_GAP")
    assert by_type(conflicts, "PREFERENCE_VIOLATION")


def test_per_weekday_minimum_staffing():
    # Needs 2 on weekdays, 1 on weekends: offs must fall on Sat/Sun.
    sc = scenario(employees=[EmployeeIn(1, "A"), EmployeeIn(2, "B")],
                  rules=[RuleIn(1, 10, (2, 2, 2, 2, 2, 1, 1))],
                  assignments=[AssignmentIn(1, 1, 10), AssignmentIn(2, 1, 10)])
    plan = RosterEngine(sc).generate()
    offs = [d for (e, d), s in plan.status.items() if s.status == WEEKLY_OFF]
    assert offs and all(d.weekday() >= 5 for d in offs)
    assert not by_type(validate(sc, plan), "COVERAGE_GAP")


def test_approved_leave_and_holiday_closure():
    xmas = date(2026, 12, 25)
    sc = scenario(employees=[EmployeeIn(1, "A"), EmployeeIn(2, "B")],
                  rules=[RuleIn(1, 10, MON_SAT, on_holidays=False)],
                  assignments=[AssignmentIn(1, 1, 10), AssignmentIn(2, 1, 10)],
                  absences=[AbsenceIn(1, date(2026, 12, 9), date(2026, 12, 10), "PLANNED_LEAVE")],
                  holidays={xmas: "Christmas"})
    plan = RosterEngine(sc).generate()
    assert plan.status[(1, date(2026, 12, 9))].status == LEAVE
    assert plan.status[(1, xmas)].status == PUBLIC_HOLIDAY
    assert sc.demand(1, 10, xmas) == 0
    assert not by_type(validate(sc, plan), "COVERAGE_GAP")


def test_date_override_raises_requirement():
    sale = date(2026, 12, 11)
    sc = scenario(employees=[EmployeeIn(1, "A")], rules=[RuleIn(1, 10, MON_SAT)],
                  assignments=[AssignmentIn(1, 1, 10)], overrides={(1, 10, sale): (2, "Sale")})
    gaps = by_type(validate(sc, RosterEngine(sc).generate()), "COVERAGE_GAP")
    assert [g["roster_date"] for g in gaps] == [sale]


def test_multi_brand_employee_is_not_falsely_double_booked():
    # Regression: the old generator gave both brands' first process the same 09-11 slot.
    sc = scenario(employees=[EmployeeIn(1, "A")], rules=[RuleIn(1, 10, MON_SAT), RuleIn(2, 10, MON_SAT)],
                  assignments=[AssignmentIn(1, 1, 10), AssignmentIn(1, 2, 10)])
    plan = RosterEngine(sc).generate()
    assert not by_type(validate(sc, plan), "COVERAGE_GAP")
    assert not by_type(validate(sc, plan), "INCOMPATIBLE_SHIFT")


def test_incompatible_shift_detected():
    sc = scenario(employees=[EmployeeIn(1, "A")],
                  rules=[RuleIn(1, 10, MON_SAT, shift_start=time(7), shift_end=time(15)),
                         RuleIn(2, 10, MON_SAT, shift_start=time(14), shift_end=time(22))],
                  assignments=[AssignmentIn(1, 1, 10), AssignmentIn(1, 2, 10)])
    assert by_type(validate(sc, RosterEngine(sc).generate()), "INCOMPATIBLE_SHIFT")


def test_manual_edit_validation_flags_leave_conflict_and_lost_coverage():
    sc = scenario(employees=[EmployeeIn(1, "A"), EmployeeIn(2, "B")], rules=[RuleIn(1, 10, MON_SAT)],
                  assignments=[AssignmentIn(1, 1, 10)],
                  absences=[AbsenceIn(1, date(2026, 12, 9), date(2026, 12, 9), "PLANNED_LEAVE")])
    plan = RosterEngine(sc).generate()
    plan.status[(1, date(2026, 12, 9))] = DayState(WORKING, "MANUAL")
    plan.status[(1, date(2026, 12, 10))] = DayState(WEEKLY_OFF, "MANUAL")
    conflicts = validate(sc, plan)
    assert by_type(conflicts, "LEAVE_CONFLICT")
    assert [c["roster_date"] for c in by_type(conflicts, "COVERAGE_GAP")] == [date(2026, 12, 10)]


def test_locked_cells_are_respected_by_regeneration():
    sc = scenario(employees=[EmployeeIn(1, "A"), EmployeeIn(2, "B")], rules=[RuleIn(1, 10, ALL_WEEK)],
                  assignments=[AssignmentIn(1, 1, 10), AssignmentIn(2, 1, 10)])
    key = (1, date(2026, 12, 8))
    plan = RosterEngine(sc).generate(locked={key: DayState(WEEKLY_OFF, "MANUAL", "swap")})
    assert plan.status[key].status == WEEKLY_OFF and plan.status[key].source == "MANUAL"
    assert plan.is_working(2, date(2026, 12, 8))


def test_one_absence_hitting_two_brands_is_reported():
    d = date(2026, 12, 9)
    sc = scenario(employees=[EmployeeIn(1, "A")], rules=[RuleIn(1, 10, MON_SAT), RuleIn(2, 10, MON_SAT)],
                  assignments=[AssignmentIn(1, 1, 10), AssignmentIn(1, 2, 10)],
                  absences=[AbsenceIn(1, d, d, "UNAVAILABLE")])
    conflicts = validate(sc, RosterEngine(sc).generate())
    assert len([c for c in by_type(conflicts, "COVERAGE_GAP") if c["roster_date"] == d]) == 2
    assert by_type(conflicts, "MULTI_BRAND_IMPACT")


def test_cover_while_off_is_double_booking():
    d = date(2026, 12, 9)
    sc = scenario(employees=[EmployeeIn(1, "A"), EmployeeIn(2, "B")], rules=[RuleIn(1, 10, MON_SAT)],
                  assignments=[AssignmentIn(1, 1, 10)])
    plan = RosterEngine(sc).generate()
    plan.status[(2, d)] = DayState(WEEKLY_OFF, "MANUAL")
    plan.covers.append(Cover(2, 1, 10, d, "MANUAL"))
    assert by_type(validate(sc, plan), "DOUBLE_BOOKING")
