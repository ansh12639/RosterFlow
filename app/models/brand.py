from datetime import datetime

from sqlalchemy.dialects.mysql import BIGINT
from ..extensions import db


class Brand(db.Model):
    __tablename__ = "brands"

    id = db.Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)

    name = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    active = db.Column(db.Boolean, nullable=False, default=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<Brand {self.name}>"
