from datetime import datetime

from sqlalchemy.dialects.mysql import BIGINT, ENUM
from ..extensions import db


class Conflict(db.Model):
    __tablename__ = "conflicts"

    id = db.Column(BIGINT(unsigned=True), primary_key=True)

    roster_version_id = db.Column(
        BIGINT(unsigned=True),
        db.ForeignKey("roster_versions.id", ondelete="CASCADE"),
        nullable=False,
    )

    roster_date = db.Column(db.Date, nullable=False)

    brand_id = db.Column(
        BIGINT(unsigned=True),
        db.ForeignKey("brands.id", ondelete="SET NULL"),
        nullable=True,
    )

    process_id = db.Column(
        BIGINT(unsigned=True),
        db.ForeignKey("processes.id", ondelete="SET NULL"),
        nullable=True,
    )

    employee_id = db.Column(
        BIGINT(unsigned=True),
        db.ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
    )

    conflict_type = db.Column(
        ENUM(
            "COVERAGE_GAP",
            "DOUBLE_BOOKING",
            "LEAVE_CONFLICT",
            "RULE_VIOLATION",
            "UNASSIGNED_REQUIREMENT",
        ),
        nullable=False,
    )

    severity = db.Column(
        ENUM("ERROR", "WARNING", "INFO"), nullable=False, default="ERROR"
    )

    required_staff = db.Column(db.Integer, nullable=True)
    available_staff = db.Column(db.Integer, nullable=True)

    message = db.Column(db.Text, nullable=False)
    resolved = db.Column(db.Boolean, nullable=False, default=False)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    version = db.relationship("RosterVersion")
    brand = db.relationship("Brand")
    process = db.relationship("Process")
    employee = db.relationship("Employee")
