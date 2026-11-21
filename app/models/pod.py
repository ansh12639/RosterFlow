from datetime import datetime

from ..extensions import db
from .types import ID


class Pod(db.Model):
    __tablename__ = "pods"

    id = db.Column(ID, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    lead_employee_id = db.Column(
        ID,
        db.ForeignKey("employees.id", ondelete="SET NULL", use_alter=True, name="fk_pod_lead"),
        nullable=True,
    )
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    employees = db.relationship(
        "Employee", back_populates="pod", foreign_keys="Employee.pod_id"
    )
    lead_employee = db.relationship(
        "Employee", back_populates="led_pods", foreign_keys=[lead_employee_id]
    )

    def __repr__(self):
        return f"<Pod {self.name}>"
