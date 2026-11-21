from sqlalchemy.dialects.mysql import BIGINT
from ..extensions import db


class WorkingRule(db.Model):
    __tablename__ = "working_rules"

    id = db.Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)

    brand_id = db.Column(
        BIGINT(unsigned=True), db.ForeignKey("brands.id"), nullable=False
    )

    process_id = db.Column(
        BIGINT(unsigned=True), db.ForeignKey("processes.id"), nullable=False
    )

    rule_name = db.Column(db.String(120), nullable=False)

    operates_sunday = db.Column(db.Boolean, nullable=False, default=False)

    operates_public_holidays = db.Column(db.Boolean, nullable=False, default=False)

    operates_monday_to_saturday = db.Column(db.Boolean, nullable=False, default=True)

    minimum_staff = db.Column(db.Integer, nullable=False, default=1)

    effective_from = db.Column(db.Date, nullable=False)
    effective_to = db.Column(db.Date, nullable=True)

    active = db.Column(db.Boolean, nullable=False, default=True)

    brand = db.relationship("Brand")
    process = db.relationship("Process")

    def __repr__(self):
        return f"<WorkingRule {self.rule_name}>"
