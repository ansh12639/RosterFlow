import json
from datetime import datetime

from ..extensions import db
from .types import ID

CONFLICT_TYPES = (
    "COVERAGE_GAP",
    "UNASSIGNED_REQUIREMENT",
    "MULTI_BRAND_IMPACT",
    "DOUBLE_BOOKING",
    "INCOMPATIBLE_SHIFT",
    "LEAVE_CONFLICT",
    "RULE_VIOLATION",
    "REST_VIOLATION",
    "PREFERENCE_VIOLATION",
    "COMP_OFF_ELIGIBLE",
)


class Conflict(db.Model):
    __tablename__ = "conflicts"
    __table_args__ = (
        db.Index("idx_conflict_version_status", "roster_version_id", "resolved", "severity"),
    )

    id = db.Column(ID, primary_key=True, autoincrement=True)
    roster_version_id = db.Column(
        ID, db.ForeignKey("roster_versions.id", ondelete="CASCADE"), nullable=False
    )
    roster_date = db.Column(db.Date, nullable=False)
    brand_id = db.Column(ID, db.ForeignKey("brands.id", ondelete="SET NULL"), nullable=True)
    process_id = db.Column(ID, db.ForeignKey("processes.id", ondelete="SET NULL"), nullable=True)
    employee_id = db.Column(ID, db.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True)
    conflict_type = db.Column(db.Enum(*CONFLICT_TYPES, name="conflict_type"), nullable=False)
    severity = db.Column(
        db.Enum("ERROR", "WARNING", "INFO", name="conflict_severity"), nullable=False, default="ERROR"
    )
    required_staff = db.Column(db.Integer, nullable=True)
    available_staff = db.Column(db.Integer, nullable=True)
    message = db.Column(db.Text, nullable=False)
    suggestion = db.Column(db.Text, nullable=True)
    candidates_json = db.Column(db.Text, nullable=True)
    ai_explanation = db.Column(db.Text, nullable=True)
    resolved = db.Column(db.Boolean, nullable=False, default=False)  # acknowledged by manager
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    version = db.relationship("RosterVersion", backref=db.backref("conflicts", passive_deletes=True))
    brand = db.relationship("Brand")
    process = db.relationship("Process")
    employee = db.relationship("Employee")

    @property
    def candidates(self):
        try:
            return json.loads(self.candidates_json or "[]")
        except ValueError:
            return []

    @property
    def key(self):
        return (self.conflict_type, self.roster_date, self.brand_id, self.process_id, self.employee_id)
