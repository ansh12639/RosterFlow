"""RosterFlow scheduling core.

Pure-Python package (no Flask / SQLAlchemy imports in ``scenario``, ``engine`` and
``validator``) so the scheduling logic can be unit-tested and reasoned about in
isolation. ``loader`` and ``store`` translate between the database and this core.
"""
