from calendar import monthrange
from datetime import date, datetime, time, timedelta

from sqlalchemy import or_

from app.models import (
    Employee,
    Assignment,
    WorkingRule,
    Availability,
    EmployeeWeeklyOff,
    Holiday,
)


class RosterGenerator:
    """
    Shift-aware monthly roster generator.

    Features:
    - Multiple sequential process shifts per employee per day.
    - Prevents overlapping shifts.
    - Checks employee assignments and effective dates.
    - Checks approved leave, comp-offs and unavailability.
    - Checks weekly offs and public holidays.
    - Respects brand/process operating calendars.
    - Detects insufficient staffing.
    - Balances employee workload.

    Note:
    Shift times are prototype assumptions and can be configured later.
    """

    SHIFT_START_HOUR = 9
    SHIFT_DURATION_HOURS = 2

    def __init__(self, year, month):

        if month < 1 or month > 12:
            raise ValueError("Month must be between 1 and 12.")

        self.year = year
        self.month = month

        self.start_date = date(year, month, 1)
        self.end_date = date(year, month, monthrange(year, month)[1])

        self.employees = []
        self.assignments = []
        self.working_rules = []
        self.availability = []
        self.weekly_offs = []
        self.holidays = []

        self.roster_entries = []
        self.conflicts = []

        self.employee_workload = {}

        self.employee_lookup = {}

    # --------------------------------------------------
    # 1. LOAD DATABASE DATA
    # --------------------------------------------------

    def load_data(self):
        """Load all scheduling inputs from MySQL."""

        self.employees = Employee.query.filter_by(active=True).all()

        self.assignments = (
            Assignment.query.filter_by(active=True)
            .filter(
                Assignment.effective_from <= self.end_date,
                or_(
                    Assignment.effective_to.is_(None),
                    Assignment.effective_to >= self.start_date,
                ),
            )
            .all()
        )

        self.working_rules = (
            WorkingRule.query.filter_by(active=True)
            .filter(
                WorkingRule.effective_from <= self.end_date,
                or_(
                    WorkingRule.effective_to.is_(None),
                    WorkingRule.effective_to >= self.start_date,
                ),
            )
            .all()
        )

        self.availability = Availability.query.filter(
            Availability.approval_status == "APPROVED",
            Availability.start_date <= self.end_date,
            Availability.end_date >= self.start_date,
        ).all()

        self.weekly_offs = EmployeeWeeklyOff.query.filter(
            EmployeeWeeklyOff.effective_from <= self.end_date,
            or_(
                EmployeeWeeklyOff.effective_to.is_(None),
                EmployeeWeeklyOff.effective_to >= self.start_date,
            ),
        ).all()

        self.holidays = Holiday.query.filter(
            Holiday.holiday_date >= self.start_date,
            Holiday.holiday_date <= self.end_date,
        ).all()

        self.employee_lookup = {employee.id: employee for employee in self.employees}

        return {
            "employees": len(self.employees),
            "assignments": len(self.assignments),
            "working_rules": len(self.working_rules),
            "availability": len(self.availability),
            "weekly_offs": len(self.weekly_offs),
            "holidays": len(self.holidays),
        }

    # --------------------------------------------------
    # 2. CHECK WHETHER PROCESS OPERATES
    # --------------------------------------------------

    def is_rule_operating(self, target_date, rule):
        """
        Determine whether a process requires coverage today.

        Closed days must not generate coverage-gap conflicts.
        """

        is_public_holiday = any(
            holiday.holiday_date == target_date for holiday in self.holidays
        )

        if is_public_holiday and not rule.operates_public_holidays:
            return False

        if target_date.weekday() == 6:
            return rule.operates_sunday

        return rule.operates_monday_to_saturday

    # --------------------------------------------------
    # 3. CHECK EMPLOYEE AVAILABILITY
    # --------------------------------------------------

    def is_employee_available(self, employee_id, target_date, rule):
        """Check leave, weekly off and working-day restrictions."""

        # Approved leave, comp-off or unavailability
        for record in self.availability:

            if (
                record.employee_id == employee_id
                and record.start_date <= target_date <= record.end_date
            ):
                return False, record.availability_type

        # Employee weekly off
        for weekly_off in self.weekly_offs:

            if (
                weekly_off.employee_id == employee_id
                and weekly_off.weekday == target_date.weekday()
                and weekly_off.effective_from <= target_date
                and (
                    weekly_off.effective_to is None
                    or weekly_off.effective_to >= target_date
                )
            ):
                return False, "WEEKLY_OFF"

        # Public holiday
        is_public_holiday = any(
            holiday.holiday_date == target_date for holiday in self.holidays
        )

        if is_public_holiday and not rule.operates_public_holidays:
            return False, "PUBLIC_HOLIDAY"

        # Sunday
        if target_date.weekday() == 6 and not rule.operates_sunday:
            return False, "SUNDAY_OFF"

        # Monday to Saturday
        if target_date.weekday() != 6 and not rule.operates_monday_to_saturday:
            return False, "NON_WORKING_DAY"

        return True, "AVAILABLE"

    # --------------------------------------------------
    # 4. CHECK ACTIVE EMPLOYEE ASSIGNMENT
    # --------------------------------------------------

    def has_active_assignment(self, employee_id, brand_id, process_id, target_date):
        """Check whether an employee is assigned to this process."""

        return any(
            assignment.employee_id == employee_id
            and assignment.brand_id == brand_id
            and assignment.process_id == process_id
            and assignment.effective_from <= target_date
            and (
                assignment.effective_to is None
                or assignment.effective_to >= target_date
            )
            for assignment in self.assignments
        )

    # --------------------------------------------------
    # 5. GENERATE PROCESS SHIFT
    # --------------------------------------------------

    def get_process_shift(self, process_index):
        """Generate a two-hour shift for a process."""

        shift_start_datetime = datetime.combine(
            self.start_date, time(self.SHIFT_START_HOUR, 0)
        ) + timedelta(hours=process_index * self.SHIFT_DURATION_HOURS)

        shift_end_datetime = shift_start_datetime + timedelta(
            hours=self.SHIFT_DURATION_HOURS
        )

        return (shift_start_datetime.time(), shift_end_datetime.time())

    # --------------------------------------------------
    # 6. CHECK SHIFT OVERLAP
    # --------------------------------------------------

    def has_shift_overlap(self, employee_id, shift_start, shift_end, daily_bookings):
        """Prevent overlapping shifts for an employee."""

        for booking in daily_bookings.get(employee_id, []):

            booked_start = booking["shift_start"]
            booked_end = booking["shift_end"]

            if shift_start < booked_end and shift_end > booked_start:
                return True

        return False

    # --------------------------------------------------
    # 7. FIND ELIGIBLE EMPLOYEES
    # --------------------------------------------------

    def get_eligible_employees(
        self,
        brand_id,
        process_id,
        target_date,
        rule,
        shift_start,
        shift_end,
        daily_bookings,
    ):
        """Find employees eligible for a particular process shift."""

        eligible_employees = []

        for assignment in self.assignments:

            if assignment.brand_id != brand_id or assignment.process_id != process_id:
                continue

            employee = self.employee_lookup.get(assignment.employee_id)

            if employee is None:
                continue

            # Check assignment effective dates
            if assignment.effective_from > target_date or (
                assignment.effective_to is not None
                and assignment.effective_to < target_date
            ):
                continue

            # Check employee availability
            available, reason = self.is_employee_available(
                employee.id, target_date, rule
            )

            if not available:
                continue

            # Prevent overlapping shifts
            if self.has_shift_overlap(
                employee.id, shift_start, shift_end, daily_bookings
            ):
                continue

            eligible_employees.append(employee)

        # Remove duplicate employees from eligible list
        unique_employees = {employee.id: employee for employee in eligible_employees}

        eligible_employees = list(unique_employees.values())

        # Prioritize employees with lower monthly workload
        eligible_employees.sort(
            key=lambda employee: (
                self.employee_workload.get(employee.id, 0),
                employee.id,
            )
        )

        return eligible_employees

    # --------------------------------------------------
    # 8. BUILD MONTHLY ROSTER
    # --------------------------------------------------

    def build_roster(self):
        """Generate monthly roster entries and conflicts."""

        self.roster_entries = []
        self.conflicts = []

        self.employee_workload = {employee.id: 0 for employee in self.employees}

        # Group rules by brand
        rules_by_brand = {}

        for rule in self.working_rules:

            rules_by_brand.setdefault(rule.brand_id, []).append(rule)

        # Sort processes consistently within each brand
        for brand_id in rules_by_brand:

            rules_by_brand[brand_id].sort(key=lambda rule: rule.process_id)

        current_date = self.start_date

        while current_date <= self.end_date:

            # Stores employee shifts for this date
            daily_bookings = {}

            for brand_id, brand_rules in rules_by_brand.items():

                for process_index, rule in enumerate(brand_rules):

                    # Check rule effective dates
                    if rule.effective_from > current_date or (
                        rule.effective_to is not None
                        and rule.effective_to < current_date
                    ):
                        continue

                    # IMPORTANT: Skip closed operating days
                    if not self.is_rule_operating(current_date, rule):
                        continue

                    shift_start, shift_end = self.get_process_shift(process_index)

                    eligible_employees = self.get_eligible_employees(
                        brand_id=brand_id,
                        process_id=rule.process_id,
                        target_date=current_date,
                        rule=rule,
                        shift_start=shift_start,
                        shift_end=shift_end,
                        daily_bookings=daily_bookings,
                    )

                    selected_employees = eligible_employees[: rule.minimum_staff]

                    # Create roster entries
                    for employee in selected_employees:

                        self.roster_entries.append(
                            {
                                "employee_id": employee.id,
                                "brand_id": rule.brand_id,
                                "process_id": rule.process_id,
                                "roster_date": current_date,
                                "shift_start": shift_start,
                                "shift_end": shift_end,
                                "status": "WORKING",
                                "source": "AUTO",
                            }
                        )

                        daily_bookings.setdefault(employee.id, []).append(
                            {
                                "shift_start": shift_start,
                                "shift_end": shift_end,
                                "brand_id": rule.brand_id,
                                "process_id": rule.process_id,
                            }
                        )

                        self.employee_workload[employee.id] += 1

                    # Detect insufficient staffing
                    if len(selected_employees) < rule.minimum_staff:

                        self.conflicts.append(
                            {
                                "roster_date": current_date,
                                "brand_id": rule.brand_id,
                                "process_id": rule.process_id,
                                "employee_id": None,
                                "conflict_type": "COVERAGE_GAP",
                                "severity": "ERROR",
                                "required_staff": rule.minimum_staff,
                                "available_staff": len(eligible_employees),
                                "resolved": False,
                                "message": (
                                    f"Required {rule.minimum_staff} employees "
                                    f"for this process, but only "
                                    f"{len(eligible_employees)} eligible "
                                    f"employees were available."
                                ),
                            }
                        )

            current_date += timedelta(days=1)

        return {
            "total_roster_entries": len(self.roster_entries),
            "total_conflicts": len(self.conflicts),
            "employee_workload": self.employee_workload,
        }

    # --------------------------------------------------
    # 9. MAIN GENERATION METHOD
    # --------------------------------------------------

    def generate(self):
        """Load data and generate the monthly roster."""

        data_summary = self.load_data()

        roster_summary = self.build_roster()

        return {
            "month": self.month,
            "year": self.year,
            "data": data_summary,
            "roster": roster_summary,
            "entries": self.roster_entries,
            "conflicts": self.conflicts,
        }
