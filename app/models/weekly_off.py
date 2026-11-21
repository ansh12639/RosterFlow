from datetime import datetime

from sqlalchemy.dialects.mysql import BIGINT
from ..extensions import db


class EmployeeWeeklyOff(db.Model):
    __tablename__ = "employee_weekly_offs"

    id = db.Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)

    employee_id = db.Column(
        BIGINT(unsigned=True),
        db.ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
    )

    weekday = db.Column(db.Integer, nullable=False)

    effective_from = db.Column(db.Date, nullable=False)
    effective_to = db.Column(db.Date, nullable=True)

    employee = db.relationship("Employee")

    def __repr__(self):
        return f"<WeeklyOff employee={self.employee_id} weekday={self.weekday}>"
