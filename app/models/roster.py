from datetime import datetime

from ..extensions import db
from .types import ID

DAY_STATUSES = (
    "WORKING",
    "WEEKLY_OFF",
    "PUBLIC_HOLIDAY",
    "LEAVE",
    "COMP_OFF",
    "UNAVAILABLE",
    "UNASSIGNED",
)


class RosterVersion(db.Model):
    __tablename__ = "roster_versions"
    __table_args__ = (
        db.UniqueConstraint("roster_month", "version_number", name="uq_roster_month_version"),
    )

    id = db.Column(ID, primary_key=True, autoincrement=True)
    roster_month = db.Column(db.Date, nullable=False)
    version_number = db.Column(db.Integer, nullable=False)
    status = db.Column(
        db.Enum("DRAFT", "PUBLISHED", "ARCHIVED", name="roster_status"),
        nullable=False,
        default="DRAFT",
    )
    parent_version_id = db.Column(ID, db.ForeignKey("roster_versions.id", ondelete="SET NULL"), nullable=True)
    generated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    published_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    parent = db.relationship("RosterVersion", remote_side=[id])

    @property
    def label(self):
        return f"{self.roster_month.strftime('%B %Y')} · V{self.version_number}"

    @property
    def editable(self):
        return self.status == "DRAFT"


class RosterDay(db.Model):
    """What an employee is doing on a date (working / off / leave ...)."""

    __tablename__ = "roster_days"
    __table_args__ = (
        db.UniqueConstraint("roster_version_id", "employee_id", "roster_date", name="uq_roster_day"),
        db.Index("idx_roster_day_date", "roster_version_id", "roster_date"),
    )

    id = db.Column(ID, primary_key=True, autoincrement=True)
    roster_version_id = db.Column(
        ID, db.ForeignKey("roster_versions.id", ondelete="CASCADE"), nullable=False
    )
    employee_id = db.Column(ID, db.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    roster_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.Enum(*DAY_STATUSES, name="roster_day_status"), nullable=False)
    source = db.Column(db.Enum("AUTO", "MANUAL", name="roster_day_source"), nullable=False, default="AUTO")
    note = db.Column(db.String(255), nullable=True)

    employee = db.relationship("Employee")


class RosterEntry(db.Model):
    """A brand/process duty performed by a working employee on a date."""

    __tablename__ = "roster_entries"
    __table_args__ = (
        db.Index("idx_roster_date_scope", "roster_version_id", "roster_date", "brand_id", "process_id"),
        db.Index("idx_roster_employee_date", "roster_version_id", "employee_id", "roster_date"),
    )

    id = db.Column(ID, primary_key=True, autoincrement=True)
    roster_version_id = db.Column(
        ID, db.ForeignKey("roster_versions.id", ondelete="CASCADE"), nullable=False
    )
    employee_id = db.Column(ID, db.ForeignKey("employees.id"), nullable=False)
    brand_id = db.Column(ID, db.ForeignKey("brands.id"), nullable=False)
    process_id = db.Column(ID, db.ForeignKey("processes.id"), nullable=False)
    roster_date = db.Column(db.Date, nullable=False)
    shift_start = db.Column(db.Time, nullable=True)
    shift_end = db.Column(db.Time, nullable=True)
    status = db.Column(
        db.Enum("WORKING", "WEEKLY_OFF", "PUBLIC_HOLIDAY", "LEAVE", "COMP_OFF", "UNASSIGNED", name="roster_entry_status"),
        nullable=False,
        default="WORKING",
    )
    source = db.Column(db.Enum("AUTO", "MANUAL", name="roster_entry_source"), nullable=False, default="AUTO")
    is_cover = db.Column(db.Boolean, nullable=False, default=False)

    employee = db.relationship("Employee")
    brand = db.relationship("Brand")
    process = db.relationship("Process")
    version = db.relationship("RosterVersion", backref=db.backref("entries", passive_deletes=True))


class RosterChangeLog(db.Model):
    """Audit trail of every manual change to a roster version."""

    __tablename__ = "roster_change_log"

    id = db.Column(ID, primary_key=True, autoincrement=True)
    roster_version_id = db.Column(
        ID, db.ForeignKey("roster_versions.id", ondelete="CASCADE"), nullable=False
    )
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    action = db.Column(db.String(40), nullable=False)
    description = db.Column(db.Text, nullable=False)
