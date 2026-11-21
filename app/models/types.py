"""Column types shared by all models.

MySQL is the production database (unsigned BIGINT keys, native ENUMs), but the
same models must also run on SQLite so the test-suite needs no database server.
``with_variant`` gives each dialect the type it handles best.
"""
from sqlalchemy import BigInteger, Integer
from sqlalchemy.dialects import mysql

ID = (
    BigInteger()
    .with_variant(mysql.BIGINT(unsigned=True), "mysql")
    .with_variant(Integer(), "sqlite")
)
