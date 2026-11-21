from datetime import time

from ..extensions import db
from .types import ID

WEEKDAY_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class WorkingRule(db.Model):
    """Operating calendar + minimum staffing for one brand/process.

    ``daily_minimums`` holds seven comma separated integers (Mon..Sun). A 0 means
    the process is closed that weekday, so one column expresses both the operating
    days and day-specific minimum staffing (e.g. "2,2,2,2,2,1,1").
    """

    __tablename__ = "working_rules"
    __table_args__ = (
        db.Index("idx_rule_lookup", "brand_id", "process_id", "active", "effective_from"),
    )

    id = db.Column(ID, primary_key=True, autoincrement=True)
    brand_id = db.Column(ID, db.ForeignKey("brands.id"), nullable=False)
    process_id = db.Column(ID, db.ForeignKey("processes.id"), nullable=False)
    rule_name = db.Column(db.String(120), nullable=False)

    daily_minimums = db.Column(db.String(40), nullable=False, default="1,1,1,1,1,1,0")
    operates_public_holidays = db.Column(db.Boolean, nullable=False, default=False)
    shift_start = db.Column(db.Time, nullable=False, default=time(10, 0))
    shift_end = db.Column(db.Time, nullable=False, default=time(19, 0))

    effective_from = db.Column(db.Date, nullable=False)
    effective_to = db.Column(db.Date, nullable=True)
    active = db.Column(db.Boolean, nullable=False, default=True)

    brand = db.relationship("Brand")
    process = db.relationship("Process")

    @property
    def minimums(self):
        values = [int(v) for v in (self.daily_minimums or "").split(",") if v.strip() != ""]
        return tuple((values + [0] * 7)[:7])

    @minimums.setter
    def minimums(self, values):
        self.daily_minimums = ",".join(str(max(0, int(v))) for v in values)

    @property
    def operating_days_label(self):
        open_days = [i for i, v in enumerate(self.minimums) if v > 0]
        if len(open_days) == 7:
            days = "7 days"
        elif open_days == list(range(6)):
            days = "Mon–Sat"
        elif open_days == list(range(5)):
            days = "Mon–Fri"
        else:
            days = ", ".join(WEEKDAY_SHORT[i] for i in open_days) or "Closed"
        return days

    @property
    def schedule_label(self):
        open_days = [i for i, v in enumerate(self.minimums) if v > 0]
        if len(open_days) == 7 and self.operates_public_holidays:
            return "365-day operations"
        suffix = "incl. public holidays" if self.operates_public_holidays else "public holidays off"
        return f"{self.operating_days_label}, {suffix}"

    def __repr__(self):
        return f"<WorkingRule {self.rule_name}>"


class CoverageOverride(db.Model):
    """Date-specific staffing requirement (sale days, launches, closures)."""

    __tablename__ = "coverage_overrides"
    __table_args__ = (
        db.UniqueConstraint("brand_id", "process_id", "override_date", name="uq_override_scope"),
    )

    id = db.Column(ID, primary_key=True, autoincrement=True)
    brand_id = db.Column(ID, db.ForeignKey("brands.id"), nullable=False)
    process_id = db.Column(ID, db.ForeignKey("processes.id"), nullable=False)
    override_date = db.Column(db.Date, nullable=False)
    minimum_staff = db.Column(db.Integer, nullable=False)  # 0 = closed that day
    reason = db.Column(db.String(150), nullable=True)

    brand = db.relationship("Brand")
    process = db.relationship("Process")
