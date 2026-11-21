from datetime import datetime

from sqlalchemy.dialects.mysql import BIGINT
from ..extensions import db


class Pod(db.Model):
    __tablename__ = "pods"

    id = db.Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)

    name = db.Column(db.String(100), unique=True, nullable=False)

    lead_employee_id = db.Column(
        BIGINT(unsigned=True),
        db.ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Employees assigned to this pod.
    employees = db.relationship(
        "Employee", back_populates="pod", foreign_keys="Employee.pod_id"
    )

    # Employee responsible for leading this pod.
    lead_employee = db.relationship(
        "Employee", back_populates="led_pods", foreign_keys=[lead_employee_id]
    )

    def __repr__(self):
        return f"<Pod {self.name}>"
