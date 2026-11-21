from datetime import datetime

from ..extensions import db
from .types import ID

AVAILABILITY_TYPES = ("PLANNED_LEAVE", "COMP_OFF", "UNAVAILABLE")


class Availability(db.Model):
    """Leave, comp-off or other unavailability. Only APPROVED records are hard constraints."""

    __tablename__ = "availability"
    __table_args__ = (
        db.Index("idx_availability_dates", "employee_id", "start_date", "end_date", "approval_status"),
    )

    id = db.Column(ID, primary_key=True, autoincrement=True)
    employee_id = db.Column(ID, db.ForeignKey("employees.id"), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    availability_type = db.Column(
        db.Enum("WEEKLY_OFF", "PLANNED_LEAVE", "COMP_OFF", "UNAVAILABLE", name="availability_type"),
        nullable=False,
    )
    approval_status = db.Column(
        db.Enum("PENDING", "APPROVED", "REJECTED", name="approval_status"),
        nullable=False,
        default="APPROVED",
    )
    notes = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    employee = db.relationship("Employee")

    def __repr__(self):
        return f"<Availability employee={self.employee_id} type={self.availability_type}>"
