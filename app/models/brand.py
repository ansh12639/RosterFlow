from datetime import datetime

from ..extensions import db
from .types import ID


class Brand(db.Model):
    __tablename__ = "brands"

    id = db.Column(ID, primary_key=True, autoincrement=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    assignments = db.relationship("Assignment", back_populates="brand")

    @property
    def primary_employee_ids(self):
        return {
            a.employee_id for a in self.assignments if a.active and a.priority == 1
        }

    @property
    def staffing_model(self):
        count = len(self.primary_employee_ids)
        if count == 0:
            return "Unstaffed"
        return "Single resource" if count == 1 else f"Shared ({count} employees)"

    def __repr__(self):
        return f"<Brand {self.name}>"
