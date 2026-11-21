from ..extensions import db
from .types import ID


class Holiday(db.Model):
    __tablename__ = "holidays"
    __table_args__ = (
        db.UniqueConstraint("holiday_date", "region", name="uq_holiday_date_region"),
    )

    id = db.Column(ID, primary_key=True, autoincrement=True)
    holiday_date = db.Column(db.Date, nullable=False)
    name = db.Column(db.String(150), nullable=False)
    region = db.Column(db.String(100), nullable=True)

    def __repr__(self):
        return f"<Holiday {self.name}: {self.holiday_date}>"
