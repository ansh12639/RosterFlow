from datetime import datetime

from sqlalchemy.dialects.mysql import BIGINT
from ..extensions import db


class Assignment(db.Model):
    __tablename__ = "assignments"

    id = db.Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)

    employee_id = db.Column(
        BIGINT(unsigned=True), db.ForeignKey("employees.id"), nullable=False
    )

    brand_id = db.Column(
        BIGINT(unsigned=True), db.ForeignKey("brands.id"), nullable=False
    )

    process_id = db.Column(
        BIGINT(unsigned=True), db.ForeignKey("processes.id"), nullable=False
    )

    effective_from = db.Column(db.Date, nullable=False)
    effective_to = db.Column(db.Date, nullable=True)

    priority = db.Column(db.Integer, nullable=False, default=100)
    active = db.Column(db.Boolean, nullable=False, default=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    employee = db.relationship("Employee")
    brand = db.relationship("Brand")
    process = db.relationship("Process")

    def __repr__(self):
        return f"<Assignment employee={self.employee_id} brand={self.brand_id}>"
