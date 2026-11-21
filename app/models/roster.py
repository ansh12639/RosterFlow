from datetime import datetime

from sqlalchemy.dialects.mysql import BIGINT, ENUM
from ..extensions import db


class RosterVersion(db.Model):
    __tablename__ = "roster_versions"

    id = db.Column(BIGINT(unsigned=True), primary_key=True)

    roster_month = db.Column(db.Date, nullable=False)
    version_number = db.Column(db.Integer, nullable=False)

    status = db.Column(
        ENUM("DRAFT", "PUBLISHED", "ARCHIVED"), nullable=False, default="DRAFT"
    )

    generated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    published_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)


class RosterEntry(db.Model):
    __tablename__ = "roster_entries"

    id = db.Column(BIGINT(unsigned=True), primary_key=True)

    roster_version_id = db.Column(
        BIGINT(unsigned=True),
        db.ForeignKey("roster_versions.id", ondelete="CASCADE"),
        nullable=False,
    )

    employee_id = db.Column(
        BIGINT(unsigned=True), db.ForeignKey("employees.id"), nullable=False
    )

    brand_id = db.Column(
        BIGINT(unsigned=True), db.ForeignKey("brands.id"), nullable=False
    )

    process_id = db.Column(
        BIGINT(unsigned=True), db.ForeignKey("processes.id"), nullable=False
    )

    roster_date = db.Column(db.Date, nullable=False)

    shift_start = db.Column(db.Time, nullable=True)
    shift_end = db.Column(db.Time, nullable=True)

    status = db.Column(
        ENUM(
            "WORKING", "WEEKLY_OFF", "PUBLIC_HOLIDAY", "LEAVE", "COMP_OFF", "UNASSIGNED"
        ),
        nullable=False,
    )

    source = db.Column(ENUM("AUTO", "MANUAL"), nullable=False, default="AUTO")

    employee = db.relationship("Employee")
    brand = db.relationship("Brand")
    process = db.relationship("Process")
    version = db.relationship("RosterVersion", backref="entries")
