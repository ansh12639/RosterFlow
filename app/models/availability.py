from datetime import datetime

from sqlalchemy.dialects.mysql import BIGINT, ENUM
from ..extensions import db


class Availability(db.Model):
    __tablename__ = "availability"

    id = db.Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)

    employee_id = db.Column(
        BIGINT(unsigned=True), db.ForeignKey("employees.id"), nullable=False
    )

    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)

    availability_type = db.Column(
        ENUM("WEEKLY_OFF", "PLANNED_LEAVE", "COMP_OFF", "UNAVAILABLE"), nullable=False
    )

    approval_status = db.Column(
        ENUM("PENDING", "APPROVED", "REJECTED"), nullable=False, default="APPROVED"
    )

    notes = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    employee = db.relationship("Employee")

    def __repr__(self):
        return (
            f"<Availability employee={self.employee_id} type={self.availability_type}>"
        )
