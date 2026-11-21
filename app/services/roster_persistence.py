from datetime import date

from app.extensions import db
from app.models import RosterVersion, RosterEntry, Conflict


def save_roster_result(year, month, result, notes=None):
    """
    Save a generated monthly roster as a new DRAFT version.

    Existing roster versions are preserved.
    """

    roster_month = date(year, month, 1)

    try:
        # Find the latest version number for this month.
        latest_version = (
            db.session.query(db.func.max(RosterVersion.version_number))
            .filter(RosterVersion.roster_month == roster_month)
            .scalar()
        )

        next_version_number = (latest_version or 0) + 1

        # Create a new roster version.
        version = RosterVersion(
            roster_month=roster_month,
            version_number=next_version_number,
            status="DRAFT",
            notes=notes,
        )

        db.session.add(version)
        db.session.flush()

        # Save generated roster entries.
        for item in result["entries"]:
            entry = RosterEntry(
                roster_version_id=version.id,
                employee_id=item["employee_id"],
                brand_id=item["brand_id"],
                process_id=item["process_id"],
                roster_date=item["roster_date"],
                shift_start=item.get("shift_start"),
                shift_end=item.get("shift_end"),
                status=item["status"],
                source=item.get("source", "AUTO"),
            )

            db.session.add(entry)

        # Save detected conflicts.
        for item in result["conflicts"]:
            conflict = Conflict(
                roster_version_id=version.id,
                roster_date=item["roster_date"],
                brand_id=item.get("brand_id"),
                process_id=item.get("process_id"),
                employee_id=item.get("employee_id"),
                conflict_type=item["conflict_type"],
                severity=item.get("severity", "ERROR"),
                required_staff=item.get("required_staff"),
                available_staff=item.get("available_staff"),
                message=item["message"],
                resolved=item.get("resolved", False),
            )

            db.session.add(conflict)

        # Commit the complete version and its records together.
        db.session.commit()

        return {
            "success": True,
            "version_id": version.id,
            "version_number": version.version_number,
            "roster_month": roster_month,
            "saved_entries": len(result["entries"]),
            "saved_conflicts": len(result["conflicts"]),
            "status": version.status,
        }

    except Exception:
        db.session.rollback()
        raise
