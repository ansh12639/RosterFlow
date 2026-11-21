from ..extensions import db
from .types import ID


class EmployeeWeeklyOff(db.Model):
    """Weekly-off pattern for an employee.

    FIXED      -> hard constraint (contractual), the employee never works that weekday.
    PREFERRED  -> soft constraint; granted when coverage allows, otherwise the
                  scheduler moves the off to another day and raises a warning.
    """

    __tablename__ = "employee_weekly_offs"
    __table_args__ = (
        db.Index("idx_weekly_off_employee_dates", "employee_id", "effective_from", "effective_to"),
    )

    id = db.Column(ID, primary_key=True, autoincrement=True)
    employee_id = db.Column(
        ID, db.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    weekday = db.Column(db.Integer, nullable=False)  # 0=Monday .. 6=Sunday
    kind = db.Column(
        db.Enum("FIXED", "PREFERRED", name="weekly_off_kind"), nullable=False, default="PREFERRED"
    )
    effective_from = db.Column(db.Date, nullable=False)
    effective_to = db.Column(db.Date, nullable=True)

    employee = db.relationship("Employee")

    def __repr__(self):
        return f"<WeeklyOff employee={self.employee_id} weekday={self.weekday}>"
