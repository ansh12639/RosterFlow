from sqlalchemy.dialects.mysql import BIGINT
from ..extensions import db


class Process(db.Model):
    __tablename__ = "processes"

    id = db.Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)

    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    active = db.Column(db.Boolean, nullable=False, default=True)

    def __repr__(self):
        return f"<Process {self.code}: {self.name}>"
