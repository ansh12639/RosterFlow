from datetime import datetime

from sqlalchemy.dialects.mysql import BIGINT
from ..extensions import db


class Employee(db.Model):
    __tablename__ = "employees"

    id = db.Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)

    employee_code = db.Column(db.String(30), unique=True, nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(190), unique=True, nullable=False)
    phone = db.Column(db.String(30), nullable=True)

    pod_id = db.Column(
        BIGINT(unsigned=True),
        db.ForeignKey("pods.id", ondelete="SET NULL"),
        nullable=True,
    )

    active = db.Column(db.Boolean, nullable=False, default=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Employee belongs to one pod.
    pod = db.relationship("Pod", back_populates="employees", foreign_keys=[pod_id])

    # An employee may lead one or more pods.
    led_pods = db.relationship(
        "Pod", back_populates="lead_employee", foreign_keys="Pod.lead_employee_id"
    )

    def __repr__(self):
        return f"<Employee {self.employee_code}: {self.full_name}>"
