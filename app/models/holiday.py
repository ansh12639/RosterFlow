from sqlalchemy.dialects.mysql import BIGINT
from ..extensions import db


class Holiday(db.Model):
    __tablename__ = "holidays"

    id = db.Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)

    holiday_date = db.Column(db.Date, nullable=False)
    name = db.Column(db.String(150), nullable=False)
    region = db.Column(db.String(100), nullable=True)

    def __repr__(self):
        return f"<Holiday {self.name}: {self.holiday_date}>"
