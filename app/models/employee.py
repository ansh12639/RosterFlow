from datetime import datetime

from ..extensions import db
from .types import ID


class Employee(db.Model):
    __tablename__ = "employees"

    id = db.Column(ID, primary_key=True, autoincrement=True)
    employee_code = db.Column(db.String(30), unique=True, nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(190), unique=True, nullable=False)
    phone = db.Column(db.String(30), nullable=True)
    designation = db.Column(db.String(80), nullable=True)

    pod_id = db.Column(ID, db.ForeignKey("pods.id", ondelete="SET NULL"), nullable=True)

    # Mandatory rest: number of weekly offs the scheduler must give every week.
    weekly_offs_per_week = db.Column(db.Integer, nullable=False, default=1)

    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    pod = db.relationship("Pod", back_populates="employees", foreign_keys=[pod_id])
    led_pods = db.relationship(
        "Pod", back_populates="lead_employee", foreign_keys="Pod.lead_employee_id"
    )
    assignments = db.relationship("Assignment", back_populates="employee")

    @property
    def initials(self):
        return "".join(part[0] for part in self.full_name.split()[:2]).upper()

    def __repr__(self):
        return f"<Employee {self.employee_code}: {self.full_name}>"
