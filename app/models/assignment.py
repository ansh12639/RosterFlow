from datetime import datetime

from ..extensions import db
from .types import ID

PRIMARY = 1
BACKUP = 2


class Assignment(db.Model):
    """Links an employee to a brand + process.

    ``priority`` 1 = primary owner (counts towards coverage when working),
    2+ = designated backup (only used to cover gaps).
    """

    __tablename__ = "assignments"
    __table_args__ = (
        db.Index("idx_assignment_scope", "brand_id", "process_id", "active"),
        db.Index("idx_assignment_employee_dates", "employee_id", "effective_from", "effective_to"),
    )

    id = db.Column(ID, primary_key=True, autoincrement=True)
    employee_id = db.Column(ID, db.ForeignKey("employees.id"), nullable=False)
    brand_id = db.Column(ID, db.ForeignKey("brands.id"), nullable=False)
    process_id = db.Column(ID, db.ForeignKey("processes.id"), nullable=False)
    effective_from = db.Column(db.Date, nullable=False)
    effective_to = db.Column(db.Date, nullable=True)
    priority = db.Column(db.Integer, nullable=False, default=PRIMARY)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    employee = db.relationship("Employee", back_populates="assignments")
    brand = db.relationship("Brand", back_populates="assignments")
    process = db.relationship("Process")

    @property
    def role(self):
        return "Primary" if self.priority == PRIMARY else "Backup"

    def __repr__(self):
        return f"<Assignment employee={self.employee_id} brand={self.brand_id}>"
